import json
import os
import tempfile
import shutil

from datetime import datetime

from django.views.generic.base import View, TemplateView
from django.views.generic.edit import FormView
from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from django.core.files import File
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin

from ledger.accounts.models import EmailUser, Profile, Document
from ledger.accounts.forms import EmailUserForm, AddressForm, ProfileForm

from wildlifelicensing.apps.main.models import WildlifeLicenceType
from wildlifelicensing.apps.main.forms import IdentificationForm

from wildlifelicensing.apps.applications.models import Application, AmendmentRequest
from wildlifelicensing.apps.applications.utils import create_data_from_form, get_all_filenames_from_application_data, \
    prepend_url_to_application_data_files, set_app_session_data, is_app_session_data_set, get_app_session_data, \
    delete_app_session_data, determine_applicant, SessionDataMissingException, clone_application_for_renewal
from wildlifelicensing.apps.applications.forms import ProfileSelectionForm
from wildlifelicensing.apps.applications.mixins import UserCanEditApplicationMixin
from wildlifelicensing.apps.main.mixins import OfficerRequiredMixin, OfficerOrCustomerRequiredMixin
from wildlifelicensing.apps.main.helpers import is_officer, is_customer

APPLICATION_SCHEMA_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))

LICENCE_TYPE_NUM_CHARS = 2
LODGEMENT_NUMBER_NUM_CHARS = 6


class ApplicationEntryBaseView(TemplateView):
    login_url = '/'

    def get_context_data(self, **kwargs):
        kwargs['licence_type'] = get_object_or_404(WildlifeLicenceType, code=self.args[0])

        if is_officer(self.request.user) and is_app_session_data_set(self.request.session, 'customer_pk'):
            kwargs['customer'] = EmailUser.objects.get(pk=get_app_session_data(self.request.session, 'customer_pk'))

        kwargs['is_renewal'] = False
        if len(self.args) > 1:
            try:
                application = Application.objects.get(pk=self.args[1])
                if application.processing_status == 'renewal':
                    kwargs['is_renewal'] = True
            except Exception:
                pass

        return super(ApplicationEntryBaseView, self).get_context_data(**kwargs)


class NewApplicationView(OfficerOrCustomerRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        delete_app_session_data(request.session)

        set_app_session_data(request.session, 'temp_files_dir', tempfile.mkdtemp(dir=settings.MEDIA_ROOT))

        if is_customer(request.user):
            set_app_session_data(request.session, 'customer_pk', request.user.pk)

            return redirect('applications:select_licence_type', *args, **kwargs)
        else:
            return redirect('applications:create_select_customer')


class EditApplicationView(UserCanEditApplicationMixin, View):
    def get(self, request, *args, **kwargs):
        delete_app_session_data(request.session)

        temp_files_dir = tempfile.mkdtemp(dir=settings.MEDIA_ROOT)
        set_app_session_data(request.session, 'temp_files_dir', temp_files_dir)

        application = get_object_or_404(Application, pk=args[1]) if len(args) > 1 else None
        if application is not None:
            set_app_session_data(request.session, 'customer_pk', application.applicant_profile.user.pk)
            set_app_session_data(request.session, 'profile_pk', application.applicant_profile.pk)
            set_app_session_data(request.session, 'data', application.data)

            # copy document files into temp_files_dir
            for document in application.documents.all():
                shutil.copyfile(document.file.path, os.path.join(temp_files_dir, document.name))

            if application.hard_copy is not None:
                shutil.copyfile(application.hard_copy.file.path, os.path.join(temp_files_dir, application.hard_copy.name))

        return redirect('applications:enter_details', *args, **kwargs)


class CreateSelectCustomer(OfficerRequiredMixin, TemplateView):
    template_name = 'wl/entry/create_select_customer.html'
    login_url = '/'

    def get_context_data(self, **kwargs):
        kwargs['create_customer_form'] = EmailUserForm(email_required=False)

        return super(CreateSelectCustomer, self).get_context_data(**kwargs)

    def post(self, request, *args, **kwargs):
        if 'select' in request.POST:
            set_app_session_data(request.session, 'customer_pk', request.POST.get('customer'))
        elif 'create' in request.POST:
            create_customer_form = EmailUserForm(request.POST, email_required=False)
            if create_customer_form.is_valid():
                customer = create_customer_form.save()
                set_app_session_data(request.session, 'customer_pk', customer.id)
            else:
                context = {'licence_type': get_object_or_404(WildlifeLicenceType, code=self.args[0]),
                           'create_customer_form': create_customer_form}
                return render(request, self.template_name, context)

        return redirect('applications:select_licence_type', *args, **kwargs)


class SelectLicenceTypeView(LoginRequiredMixin, TemplateView):
    template_name = 'wl/entry/select_licence_type.html'
    login_url = '/'

    def get_context_data(self, **kwargs):
        kwargs['licence_types'] = dict([(licence_type.code, licence_type.name) for licence_type
                                        in WildlifeLicenceType.objects.all()])

        return super(SelectLicenceTypeView, self).get_context_data(**kwargs)


class CheckIdentificationRequiredView(LoginRequiredMixin, ApplicationEntryBaseView, FormView):
    template_name = 'wl/entry/upload_identification.html'
    form_class = IdentificationForm

    def get(self, *args, **kwargs):
        licence_type = get_object_or_404(WildlifeLicenceType, code=args[1])

        try:
            applicant = determine_applicant(self.request)
        except SessionDataMissingException as e:
            messages.error(self.request, e.message)
            return redirect('applications:create_select_customer')

        if licence_type.identification_required and applicant.identification is None:
            return super(CheckIdentificationRequiredView, self).get(*args, **kwargs)
        else:
            return redirect('applications:create_select_profile', args[1], **kwargs)

    def get_context_data(self, **kwargs):
        kwargs['file_types'] = ', '.join(['.' + file_ext for file_ext in IdentificationForm.VALID_FILE_TYPES])

        return super(CheckIdentificationRequiredView, self).get_context_data(**kwargs)

    def form_valid(self, form):
        try:
            applicant = determine_applicant(self.request)
        except SessionDataMissingException as e:
            messages.error(self.request, e.message)
            return redirect('applications:create_select_customer')

        if applicant.identification is not None:
            applicant.identification.delete()

        applicant.identification = Document.objects.create(file=self.request.FILES['identification_file'])
        applicant.save()

        # update any other applications for this user that are awaiting ID upload
        for application in Application.objects.filter(applicant_profile__user=applicant):
            if application.id_check_status == 'awaiting_update':
                application.id_check_status = 'updated'
                application.save()

        return redirect('applications:create_select_profile', *self.args)


class CreateSelectProfileView(LoginRequiredMixin, ApplicationEntryBaseView):
    template_name = 'wl/entry/create_select_profile.html'

    def get_context_data(self, **kwargs):
        if len(self.args) > 1:
            kwargs['application_pk'] = self.args[1]

        try:
            applicant = determine_applicant(self.request)
        except SessionDataMissingException as e:
            messages.error(self.request, e.message)
            return redirect('applications:create_select_customer')

        profile_exists = applicant.profile_set.count() > 0

        if is_app_session_data_set(self.request.session, 'profile_pk'):
            selected_profile = Profile.objects.get(id=get_app_session_data(self.request.session, 'profile_pk'))
            kwargs['profile_selection_form'] = ProfileSelectionForm(user=applicant, selected_profile=selected_profile)
        else:
            if profile_exists:
                kwargs['profile_selection_form'] = ProfileSelectionForm(user=applicant)

        if profile_exists:
            kwargs['profile_creation_form'] = ProfileForm(user=get_app_session_data(self.request.session, 'customer_pk'))
        else:
            kwargs['profile_creation_form'] = ProfileForm(initial_display_name='Default', initial_email=applicant.email,
                                                          user=get_app_session_data(self.request.session, 'customer_pk'))

        kwargs['address_form'] = AddressForm()
        kwargs['licence_type'] = get_object_or_404(WildlifeLicenceType, code=self.args[0])

        return super(CreateSelectProfileView, self).get_context_data(**kwargs)

    def post(self, request, *args, **kwargs):
        try:
            applicant = determine_applicant(request)
        except SessionDataMissingException as e:
            messages.error(request, e.message)
            return redirect('applications:create_select_customer')

        licence_type = WildlifeLicenceType.objects.get(code=args[0])

        if 'select' in request.POST:
            profile_selection_form = ProfileSelectionForm(request.POST, user=applicant)

            if profile_selection_form.is_valid():
                set_app_session_data(request.session, 'profile_pk', profile_selection_form.cleaned_data.get('profile').id)
            else:
                return render(request, self.template_name, {'licence_type': licence_type,
                                                            'profile_selection_form': profile_selection_form,
                                                            'profile_creation_form': ProfileForm(),
                                                            'address_form': AddressForm()})
        elif 'create' in request.POST:
            profile_form = ProfileForm(request.POST)
            address_form = AddressForm(request.POST)

            if profile_form.is_valid() and address_form.is_valid():
                profile = profile_form.save(commit=False)
                profile.postal_address = address_form.save()
                profile.save()

                set_app_session_data(request.session, 'profile_pk', profile.id)
            else:
                return render(request, self.template_name,
                              {'licence_type': licence_type,
                               'profile_selection_form': ProfileSelectionForm(user=request.user),
                               'profile_creation_form': profile_form, 'address_form': address_form})

        return redirect('applications:enter_details', *args)


class EnterDetailsView(UserCanEditApplicationMixin, ApplicationEntryBaseView):
    template_name = 'wl/entry/enter_details.html'

    def get_context_data(self, **kwargs):
        application = get_object_or_404(Application, pk=self.args[1]) if len(self.args) > 1 else None

        licence_type = WildlifeLicenceType.objects.get(code=self.args[0])
        if is_app_session_data_set(self.request.session, 'profile_pk'):
            profile = get_object_or_404(Profile, pk=get_app_session_data(self.request.session, 'profile_pk'))
        else:
            profile = application.applicant_profile

        with open('%s/json/%s.json' % (APPLICATION_SCHEMA_PATH, self.args[0])) as data_file:
            form_structure = json.load(data_file)

        kwargs['licence_type'] = licence_type
        kwargs['profile'] = profile
        kwargs['structure'] = form_structure

        kwargs['is_proxy_applicant'] = is_officer(self.request.user)

        if application is not None:
            kwargs['application_pk'] = application.pk
            if application.review_status == 'awaiting_amendments':
                amendments = AmendmentRequest.objects.filter(application=application).filter(status='requested')
                kwargs['amendments'] = amendments

        if is_app_session_data_set(self.request.session, 'data'):
            data = get_app_session_data(self.request.session, 'data')

            temp_files_dir = get_app_session_data(self.request.session, 'temp_files_dir')
            if temp_files_dir is not None:
                temp_files_url = settings.MEDIA_URL + os.path.basename(os.path.normpath(temp_files_dir))
                prepend_url_to_application_data_files(form_structure, data, temp_files_url)

            kwargs['data'] = data

        return super(EnterDetailsView, self).get_context_data(**kwargs)

    def post(self, request, *args, **kwargs):
        with open('%s/json/%s.json' % (APPLICATION_SCHEMA_PATH, args[0])) as data_file:
            form_structure = json.load(data_file)

        set_app_session_data(request.session, 'data', create_data_from_form(form_structure, request.POST, request.FILES))

        temp_files_dir = get_app_session_data(request.session, 'temp_files_dir')

        if 'draft' in request.POST or 'draft_continue' in request.POST:
            if len(args) > 1:
                application = get_object_or_404(Application, pk=args[1])
            else:
                application = Application()

            if is_officer(request.user):
                application.proxy_applicant = request.user

            application.data = get_app_session_data(request.session, 'data')
            application.licence_type = WildlifeLicenceType.objects.get(code=args[0])
            application.applicant_profile = get_object_or_404(Profile,
                                                              pk=get_app_session_data(request.session, 'profile_pk'))
            application.customer_status = 'draft'

            if application.processing_status != 'renewal':
                application.processing_status = 'draft'

            application.save(version_user=application.applicant_profile.user)

            # delete all existing documents for this application
            application.documents.all().delete()
            if application.hard_copy is not None:
                application.hard_copy.delete()

            # need to create documents from all the existing files that haven't been replaced
            # (saved in temp_files_dir) as well as any new ones
            try:
                for filename in get_all_filenames_from_application_data(form_structure,
                                                                        get_app_session_data(request.session, 'data')):

                    # need to be sure file is in tmp directory (as it could be a freshly attached file)
                    if os.path.exists(os.path.join(temp_files_dir, filename)):
                        document = Document.objects.create(name=filename)
                        with open(os.path.join(temp_files_dir, filename), 'rb') as doc_file:
                            document.file.save(filename, File(doc_file), save=True)
                            application.documents.add(document)
            except Exception as e:
                messages.error(request, 'There was a problem appending applications files: %s' % e)

            finally:
                try:
                    if temp_files_dir is not None:
                        shutil.rmtree(temp_files_dir)
                except (shutil.Error, OSError) as e:
                    messages.warning(request, 'There was a problem deleting temporary files: %s' % e)

            for f in request.FILES:
                if f == 'application_document':
                    application.hard_copy = Document.objects.create(name=str(request.FILES[f]), file=request.FILES[f])
                else:
                    application.documents.add(Document.objects.create(name=str(request.FILES[f]), file=request.FILES[f]))

            messages.warning(request, 'The application was saved to draft.')

            if 'draft' in request.POST:
                delete_app_session_data(request.session)
                return redirect('dashboard:home')
            else:
                return redirect('applications:enter_details', args[0], application.pk)
        else:
            if len(request.FILES) > 0:
                temp_files_dir = get_app_session_data(request.session, 'temp_files_dir')

                for f in request.FILES:
                    if f == 'application_document':
                        set_app_session_data(request.session, 'application_document', str(request.FILES[f]))

                    with open(os.path.join(temp_files_dir, str(request.FILES[f])), 'wb+') as destination:
                        for chunk in request.FILES[f].chunks():
                            destination.write(chunk)

            return redirect('applications:preview', *args)


class PreviewView(UserCanEditApplicationMixin, ApplicationEntryBaseView):
    template_name = 'wl/entry/preview.html'

    def get_context_data(self, **kwargs):
        with open('%s/json/%s.json' % (APPLICATION_SCHEMA_PATH, self.args[0])) as data_file:
            form_structure = json.load(data_file)

        licence_type = WildlifeLicenceType.objects.get(code=self.args[0])

        application = get_object_or_404(Application, pk=self.args[1]) if len(self.args) > 1 else None

        if is_app_session_data_set(self.request.session, 'profile_pk'):
            profile = get_object_or_404(Profile, pk=get_app_session_data(self.request.session, 'profile_pk'))
        else:
            profile = application.applicant_profile

        kwargs['licence_type'] = licence_type
        kwargs['profile'] = profile
        kwargs['structure'] = form_structure

        kwargs['is_proxy_applicant'] = is_officer(self.request.user)

        if len(self.args) > 1:
            kwargs['application_pk'] = self.args[1]

        if is_app_session_data_set(self.request.session, 'data'):
            data = get_app_session_data(self.request.session, 'data')

            temp_files_url = settings.MEDIA_URL + \
                os.path.basename(os.path.normpath(get_app_session_data(self.request.session, 'temp_files_dir')))

            prepend_url_to_application_data_files(form_structure, data, temp_files_url)

            kwargs['data'] = data

        return super(PreviewView, self).get_context_data(**kwargs)

    def post(self, request, *args, **kwargs):
        with open('%s/json/%s.json' % (APPLICATION_SCHEMA_PATH, args[0])) as data_file:
            form_structure = json.load(data_file)

        if len(args) > 1:
            application = get_object_or_404(Application, pk=args[1])
        else:
            application = Application()

        if is_officer(request.user):
            application.proxy_applicant = request.user

        application.data = get_app_session_data(self.request.session, 'data')
        application.licence_type = get_object_or_404(WildlifeLicenceType, code=args[0])
        application.correctness_disclaimer = request.POST.get('correctnessDisclaimer', '') == 'on'
        application.further_information_disclaimer = request.POST.get('furtherInfoDisclaimer', '') == 'on'
        application.applicant_profile = get_object_or_404(Profile, pk=get_app_session_data(request.session, 'profile_pk'))
        application.lodgement_sequence += 1
        application.lodgement_date = datetime.now().date()

        if application.customer_status == 'amendment_required':
            # this is a 're-lodged' application after some amendment were required.
            # from this point we assume that all the amendments have been amended.
            AmendmentRequest.objects.filter(application=application).filter(status='requested').update(status='amended')
            application.review_status = 'amended'
            application.processing_status = 'ready_for_action'
        else:
            if application.processing_status != 'renewal':
                application.processing_status = 'new'

        application.customer_status = 'under_review'

        # need to save application in order to get its pk
        if not application.lodgement_number:
            application.save(no_revision=True)
            application.lodgement_number = '%s-%s' % (str(application.licence_type.pk).zfill(LICENCE_TYPE_NUM_CHARS),
                                                      str(application.pk).zfill(LODGEMENT_NUMBER_NUM_CHARS))

        application.save(version_user=application.applicant_profile.user, version_comment='Details Modified')

        # delete all existing documents for this application
        application.documents.all().delete()
        if application.hard_copy is not None:
            application.hard_copy.delete()

        # if attached files were saved temporarily, add each to application as part of a Document
        temp_files_dir = get_app_session_data(request.session, 'temp_files_dir')
        try:
            for filename in get_all_filenames_from_application_data(form_structure,
                                                                    get_app_session_data(request.session, 'data')):
                document = Document.objects.create(name=filename)
                with open(os.path.join(temp_files_dir, filename), 'rb') as doc_file:
                    document.file.save(filename, File(doc_file), save=True)

                    application.documents.add(document)

            if is_app_session_data_set(request.session, 'application_document'):
                filename = get_app_session_data(request.session, 'application_document')
                document = Document.objects.create(name=filename)
                with open(os.path.join(get_app_session_data(request.session, 'temp_files_dir'), filename), 'rb') as doc_file:
                    document.file.save(filename, File(doc_file), save=True)

                    application.hard_copy = document
                    application.save(no_revision=True)

            messages.success(request, 'The application was successfully lodged.')
        except Exception as e:
            messages.error(request, 'There was a problem creating the application: %s' % e)
        finally:
            try:
                if temp_files_dir is not None:
                    shutil.rmtree(temp_files_dir)
            except (shutil.Error, OSError) as e:
                messages.warning(request, 'There was a problem deleting temporary files: %s' % e)

        delete_app_session_data(request.session)

        return redirect('dashboard:home')


class RenewLicenceView(View):  # NOTE: need a UserCanRenewLicence type mixin
    def get(self, request, *args, **kwargs):
        delete_app_session_data(request.session)

        previous_application = get_object_or_404(Application, licence=args[0])

        # check if there is already a renewal, otherwise create one
        try:
            application = Application.objects.get(previous_application=previous_application)
            if application.customer_status == 'under_review':
                messages.warning(request, 'A renewal for this licence has already been lodged and is awaiting review.')
                return redirect('dashboard:home')
        except Application.DoesNotExist:
            application = clone_application_for_renewal(previous_application)

        set_app_session_data(request.session, 'customer_pk', application.applicant_profile.user.pk)
        set_app_session_data(request.session, 'profile_pk', application.applicant_profile.pk)
        set_app_session_data(request.session, 'data', application.data)
        set_app_session_data(request.session, 'temp_files_dir', tempfile.mkdtemp(dir=settings.MEDIA_ROOT))

        return redirect('applications:enter_details', application.licence_type.code, application.pk, **kwargs)
