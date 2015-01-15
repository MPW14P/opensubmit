import os

import json
import StringIO
import shutil
import tarfile
import tempfile
import urllib
import zipfile
import inflection
import uuid

from datetime import timedelta, datetime

from django.contrib import auth, messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, SuspiciousOperation, ValidationError
from django.core.mail import mail_managers, send_mail
from django.core.urlresolvers import reverse
from django.http import HttpResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.encoding import smart_text
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.admin.views.decorators import staff_member_required
from django.forms.models import modelform_factory
from django.views.decorators.csrf import csrf_exempt

from openid2rp.django.auth import linkOpenID, preAuthenticate, AX, getOpenIDs

from forms import SettingsForm, getSubmissionForm, SubmissionFileUpdateForm
from models import user_courses, SubmissionFile, Submission, Assignment, TestMachine, Course, UserProfile, db_fixes, VMInstance
from models import inform_student, inform_course_owner, open_assignments
from settings import JOB_EXECUTOR_SECRET, MAIN_URL, LOGIN_DESCRIPTION, OPENID_PROVIDER, NOVA, DEBUG

from novaclient import exceptions as nova_exceptions


def index(request):
    if request.user.is_authenticated():
        return redirect('dashboard')

    return render(request, 'index.html', {'login_description': LOGIN_DESCRIPTION})

@login_required
def logout(request):
    auth.logout(request)
    return redirect('index')

@login_required
def settings(request):
    if request.POST:
        settingsForm = SettingsForm(request.POST, instance=request.user)
        if settingsForm.is_valid():
            settingsForm.save()
            messages.info(request, 'User settings saved.')
            return redirect('dashboard')
    else:
        settingsForm = SettingsForm(instance=request.user)
    return render(request, 'settings.html', {'settingsForm': settingsForm})


@login_required
def courses(request):
    UserProfileForm = modelform_factory(UserProfile, fields=['courses'])
    profile = UserProfile.objects.get(user=request.user)
    if request.POST:
        coursesForm = UserProfileForm(request.POST, instance=profile)
        if coursesForm.is_valid():
            coursesForm.save()
            messages.info(request, 'You choice was saved.')
            return redirect('dashboard')
    else:
        coursesForm = UserProfileForm(instance=profile)
    return render(request, 'courses.html', {'coursesForm': coursesForm})


@login_required
def dashboard(request):
    db_fixes(request.user)

    # if the user settings are not complete (e.f. adter OpenID registration), we MUST fix them first
    if not request.user.first_name or not request.user.last_name or not request.user.email:
        return redirect('settings')

    # render dashboard
    authored = request.user.authored.all().exclude(state=Submission.WITHDRAWN).order_by('-created')
    archived = request.user.authored.all().filter(state=Submission.WITHDRAWN).order_by('-created')
    username = request.user.get_full_name() + " <" + request.user.email + ">"
    return render(request, 'dashboard.html', {
        'authored': authored,
        'archived': archived,
        'user': request.user,
        'username': username,
        'assignments': open_assignments(request.user),
        'machines': TestMachine.objects.all()}
    )


@login_required
def details(request, subm_id):
    subm = get_object_or_404(Submission, pk=subm_id)
    if not (request.user in subm.authors.all() or request.user.is_staff):               # only authors should be able to look into submission details
        raise PermissionDenied()
    return render(request, 'details.html', {
        'submission': subm}
    )

@login_required
def new_vm(request, ass_id):
    ass = get_object_or_404(Assignment, pk=ass_id)
    
    if not ass.is_visible(user=request.user):
        raise Http404()
    
    # Check whether submissions are allowed.
    if not ass.can_create_submission(user=request.user):
        raise PermissionDenied("You are not allowed to create a submission for this assignment")
    
    if not ass.has_vm_support: #ass.nova_flavor or not ass.nova_image or not ass.nova_network:
        raise PermissionDenied("You have no VM power here.")
    
    if not VMInstance.objects.filter(owner=request.user, assignment=ass).count():
        vmname = inflection.parameterize(u'{ass.course.title}-{ass.title}-{user}'.format(ass=ass, user=request.user.username))
        token = uuid.uuid4()
        server = NOVA.servers.create(
            vmname,
            NOVA.images.get(ass.nova_image),
            NOVA.flavors.get(ass.nova_flavor),
            files={'/etc/assignmentinfo': 'Yo.'},
            nics=[{'net-id': ass.nova_network}],
            admin_pass='toor',
            meta={'yolo':'swag'},
            userdata=render_to_string('vm_userdata.sh', {'script_url': request.build_absolute_uri(reverse('script_vm', kwargs={'token':token}))}),
            key_name='root-at-mpw14p-10'
            )
        vm = VMInstance(uuid=server.id, owner=request.user, assignment=ass, token=token)
        vm.save()
    
    return redirect('view_vm', ass_id=ass_id)

def script_vm(request, token):
    vm = get_object_or_404(VMInstance, token=token)
    return HttpResponse(render_to_string('vm_submit.sh', {'vm': vm, 'submit_url': request.build_absolute_uri(reverse('submit_vm')) }), content_type="text/plain")

@csrf_exempt
def submit_vm(request):
    if not request.POST:
        raise PermissionDenied("Missing POST")
    
    vm = get_object_or_404(VMInstance, token=request.POST['token'])
    
    submissionFile = SubmissionFile(attachment=request.FILES['submission'])
    submission = Submission(submitter=vm.owner, assignment=vm.assignment)
    
    submissionFile.save()
    submission.state = submission.get_initial_state()
    submission.file_upload = submissionFile
    submission.save()
    
    submission.authors.add(vm.owner)  # something about m2m
    submission.save()
    
    if submission.state == Submission.SUBMITTED:
        inform_course_owner(request, submission)
    return HttpResponse('Successfully uploaded submission {}'.format(submission.pk))

@login_required
def kill_vm(request, ass_id):
    ass = get_object_or_404(Assignment, pk=ass_id)
    vm = get_object_or_404(VMInstance, assignment=ass, owner=request.user)

    try:    
        NOVA.servers.delete(vm.uuid)
    except nova_exceptions.NotFound:
        pass
    except nova_exceptions.ClientException as e: 
        if not DEBUG:
            raise ValidationError("Failed to delete VM: {}".format(repr(e)))
        else:
            raise
    except Exception as e:
        raise Exception("Failed to delete VM: {} {}".format(repr(e), type(e)))
    vm.delete()
    return redirect('dashboard')

@login_required
def vnc_vm(request, ass_id):
    ass = get_object_or_404(Assignment, pk=ass_id)
    
    if not ass.is_visible(user=request.user):
        raise Http404()
    
    vm = get_object_or_404(VMInstance, owner=request.user, assignment=ass)
    server = NOVA.servers.get(vm.uuid)
    try:
        vnc_url = server.get_vnc_console('novnc')['console']['url']
        return HttpResponse(vnc_url)
    except nova_exceptions.Conflict:
        pass
    return HttpResponse('')

@login_required
def view_vm(request, ass_id):
    ass = get_object_or_404(Assignment, pk=ass_id)
    
    if not ass.is_visible(user=request.user):
        raise Http404()
    
    return render(request, 'vnc.html', {
        'assignment': ass
    })

@login_required
def new(request, ass_id):
    ass = get_object_or_404(Assignment, pk=ass_id)

    if not ass.is_visible(user=request.user):
        raise Http404()

    # Check whether submissions are allowed.
    if not ass.can_create_submission(user=request.user):
        raise PermissionDenied("You are not allowed to create a submission for this assignment")

    # get submission form according to the assignment type
    SubmissionForm = getSubmissionForm(ass)

    # Analyze submission data
    if request.POST:
        if 'authors' in request.POST:
            authors = map(lambda s: User.objects.get(pk=int(s)), request.POST['authors'].split(','))
            if not ass.authors_valid(authors):
                raise PermissionDenied("The given list of co-authors is invalid!")

        # we need to fill all forms here, so that they can be rendered on validation errors
        submissionForm = SubmissionForm(request.user, ass, request.POST, request.FILES)
        if submissionForm.is_valid():
            submission = submissionForm.save(commit=False)   # commit=False to set submitter in the instance
            submission.submitter = request.user
            submission.assignment = ass
            submission.state = submission.get_initial_state()
            # take uploaded file from extra field
            if ass.has_attachment:
                submissionFile = SubmissionFile(attachment=submissionForm.cleaned_data['attachment'])
                submissionFile.save()
                submission.file_upload = submissionFile
            submission.save()
            submissionForm.save_m2m()               # because of commit=False, we first need to add the form-given authors
            submission.save()
            messages.info(request, "New submission saved.")
            if submission.state == Submission.SUBMITTED:
                inform_course_owner(request, submission)
            return redirect('dashboard')
        else:
            messages.error(request, "Please correct your submission information.")
    else:
        submissionForm = SubmissionForm(request.user, ass)
    return render(request, 'new.html', {'submissionForm': submissionForm,
                                        'assignment': ass})


@login_required
def update(request, subm_id):
    # Submission should only be editable by their creators
    submission = get_object_or_404(Submission, pk=subm_id)
    # Somebody may bypass the template check by sending direct POST form data
    if not submission.can_reupload():
        raise SuspiciousOperation("Update of submission %s is not allowed at this time." % str(subm_id))
    if request.user not in submission.authors.all():
        return redirect('dashboard')
    if request.POST:
        updateForm = SubmissionFileUpdateForm(request.POST, request.FILES)
        if updateForm.is_valid():
            new_file = SubmissionFile(attachment=updateForm.files['attachment'])
            new_file.save()
            # fix status of old uploaded file
            submission.file_upload.replaced_by = new_file
            submission.file_upload.save()
            # store new file for submissions
            submission.file_upload = new_file
            submission.state = submission.get_initial_state()
            submission.notes = updateForm.data['notes']
            submission.save()
            messages.info(request, 'Submission files successfully updated.')
            return redirect('dashboard')
    else:
        updateForm = SubmissionFileUpdateForm(instance=submission)
    return render(request, 'update.html', {'submissionFileUpdateForm': updateForm,
                                           'submission': submission})


@login_required
@staff_member_required
def gradingtable(request, course_id):
    gradings = {}
    course = get_object_or_404(Course, pk=course_id)
    assignments = course.assignments.all().order_by('title')
    # find all gradings per author and assignment
    for assignment in assignments:
        for submission in assignment.submissions.all().filter(state=Submission.CLOSED):
            for author in submission.authors.all():
                if author not in gradings.keys():
                    gradings[author] = {assignment.pk: submission.grading}
                else:
                    gradings[author][assignment.pk] = submission.grading
    # prepare gradings per author + assignment for rendering
    resulttable = []
    for author, gradlist in gradings.iteritems():
        columns = []
        numpassed = 0
        columns.append(author.last_name)
        columns.append(author.first_name)
        for assignment in assignments:
            if assignment.pk in gradlist:
                if gradlist[assignment.pk] is not None:
                    passed = gradlist[assignment.pk].means_passed
                    columns.append(gradlist[assignment.pk])
                    if passed:
                        numpassed += 1
                else:
                    columns.append('-')
            else:
                columns.append('-')
        columns.append("%s / %s" % (numpassed, len(assignments)))
        resulttable.append(columns)
    return render(request, 'gradingtable.html', {'course': course, 'assignments': assignments, 'resulttable': sorted(resulttable)})


@login_required
@staff_member_required
def coursearchive(request, course_id):
    course = get_object_or_404(Course, pk=course_id)
    coursename = course.title.replace(" ", "_").lower()

    # we need to create the result ZIP file in memory to not leave garbage on the server
    output = StringIO.StringIO()
    z = zipfile.ZipFile(output, 'w')

    # recurse through database and add according submitted files to in-memory archive
    coursedir = coursename
    assignments = course.assignments.order_by('title')
    for ass in assignments:
        assdir = coursedir + '/' + ass.title.replace(" ", "_").lower()
        for sub in ass.submissions.all().order_by('submitter'):
            submitter = "user" + str(sub.submitter.pk)      
            if sub.modified:
                modified = sub.modified.strftime("%Y_%m_%d_%H_%M_%S")
            else:
                modified = sub.created.strftime("%Y_%m_%d_%H_%M_%S")
            state = sub.state_for_students().replace(" ", "_").lower()
            submdir = "%s/%s/%s_%s/" % (assdir, submitter, modified, state)                  
            if sub.file_upload:
                # unpack student data to temporary directory
                # os.chroot is not working with tarfile support
                tempdir = tempfile.mkdtemp()
                if zipfile.is_zipfile(sub.file_upload.absolute_path()):
                    f = zipfile.ZipFile(sub.file_upload.absolute_path(), 'r')
                    f.extractall(tempdir)
                elif tarfile.is_tarfile(sub.file_upload.absolute_path()):
                    tar = tarfile.open(sub.file_upload.absolute_path())
                    tar.extractall(tempdir)
                    tar.close()
                else:
                    # unpacking not possible, just copy it
                    shutil.copyfile(sub.file_upload.absolute_path(), tempdir + "/" + sub.file_upload.basename())
                # Create final ZIP file
                allfiles = [(subdir, files) for (subdir, dirs, files) in os.walk(tempdir)] 
                for subdir, files in allfiles:
                    for f in files:
                        zip_relative_dir = subdir.replace(tempdir, "")     
                        z.write(subdir + "/" + f, submdir + 'student_files/%s/%s'%(zip_relative_dir, f), zipfile.ZIP_DEFLATED)

            # add text file with additional information
            info = tempfile.NamedTemporaryFile()
            info.write("Status: %s\n\n" % sub.state_for_students())
            info.write("Submitter: %s\n\n" % submitter)
            info.write("Last modification: %s\n\n" % modified)
            info.write("Authors: ")
            for auth in sub.authors.all():
                author = "user" + str(auth.pk)
                info.write("%s," % author)
            info.write("\n")
            if sub.grading:
                info.write("Grading: %s\n\n" % str(sub.grading))
            if sub.notes:
                notes = smart_text(sub.notes).encode('utf8')
                info.write("Author notes:\n-------------\n%s\n\n" % notes)
            if sub.grading_notes:
                notes = smart_text(sub.grading_notes).encode('utf8')
                info.write("Grading notes:\n--------------\n%s\n\n" % notes)
            info.flush()    # no closing here, because it disappears then
            z.write(info.name, submdir + "info.txt")
    z.close()
    # go back to start in ZIP file so that Django can deliver it
    output.seek(0)
    response = HttpResponse(output, content_type="application/x-zip-compressed")
    response['Content-Disposition'] = 'attachment; filename=%s.zip' % coursename
    return response


@login_required
def machine(request, machine_id):
    machine = get_object_or_404(TestMachine, pk=machine_id)
    try:
        config = filter(lambda x: x[1] != "", json.loads(machine.config))
    except:
        config = ""
    queue = Submission.pending_student_tests.all()
    additional = len(Submission.pending_full_tests.all())
    return render(request, 'machine.html', {'machine': machine, 'queue': queue, 'additional': additional, 'config': config})


@csrf_exempt
def machines(request, secret):
    ''' This is the view used by the executor.py scripts for putting machine details.
        A visible shared secret in the request is no problem, since the executors come
        from trusted networks. The secret only protects this view from outside foreigners.
    '''
    if secret != JOB_EXECUTOR_SECRET:
        raise PermissionDenied
    if request.method == "POST":
        try:
            # Find machine database entry for this host
            machine = TestMachine.objects.get(host=request.POST['Name'])
            machine.last_contact = datetime.now()
            machine.save()
        except:
            # Machine is not known so far, create new record
            machine = TestMachine(host=request.POST['Name'], last_contact=datetime.now())
            machine.save()
        # POST request contains all relevant machine information
        machine.config = request.POST['Config']
        machine.save()
        return HttpResponse(status=201)
    else:
        return HttpResponse(status=500)


@login_required
def withdraw(request, subm_id):
    # submission should only be deletable by their creators
    submission = get_object_or_404(Submission, pk=subm_id)
    if not submission.can_withdraw(user=request.user):
        raise PermissionDenied("Withdrawal for this assignment is no longer possible, or you are unauthorized to access that submission.")
    if "confirm" in request.POST:
        submission.state = Submission.WITHDRAWN
        submission.save()
        messages.info(request, 'Submission successfully withdrawn.')
        inform_course_owner(request, submission)
        return redirect('dashboard')
    else:
        return render(request, 'withdraw.html', {'submission': submission})


@require_http_methods(['GET', 'POST'])
def login(request):
    GET = request.GET
    POST = request.POST

    if 'authmethod' in GET:
        # first stage of OpenID authentication
        if request.GET['authmethod'] == "openid":
            return preAuthenticate(OPENID_PROVIDER, MAIN_URL + "/login?openidreturn")
        else:
            return redirect('index')

    elif 'openidreturn' in GET:
        user = auth.authenticate(openidrequest=request)

        if user.is_anonymous():
            user_name = None
            email = None

            user_sreg = user.openid_sreg
            user_ax = user.openid_ax

            # not known to the backend so far, create it transparently
            if 'nickname' in user_sreg:
                user_name = unicode(user_sreg['nickname'], 'utf-8')[:29]

            if 'email' in user_sreg:
                email = unicode(user_sreg['email'], 'utf-8')  # [:29]

            if AX.email in user_ax:
                email = unicode(user_ax[AX.email], 'utf-8')  # [:29]

            # no username given, register user with his e-mail address as username
            if not user_name and email:
                new_user = User(username=email[:29], email=email)

            # both, username and e-mail were not given, use a timestamp as username
            elif not user_name and not email:
                now = timezone.now()
                user_name = 'Anonymous %u%u%u%u' % (now.hour, now.minute,
                                                    now.second, now.microsecond)
                new_user = User(username=user_name)

            # username and e-mail were given; great - register as is
            elif user_name and email:
                new_user = User(username=user_name, email=email)

            # username given but no e-mail - at least we know how to call him
            elif user_name and not email:
                new_user = User(username=user_name)

            if AX.first in user_ax:
                new_user.first_name = unicode(user_ax[AX.first], 'utf-8')[:29]

            if AX.last in user_ax:
                new_user.last_name = unicode(user_ax[AX.last], 'utf-8')[:29]

            new_user.is_active = True
            new_user.save()

            linkOpenID(new_user, user.openid_claim)
            mail_managers('New user', str(new_user), fail_silently=True)
            messages.info(request, 'We created a new account for you. Please click again to enter the system.')
            return redirect('index')

        auth.login(request, user)
        return redirect('dashboard')
    else:
        return redirect('index')
