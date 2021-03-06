from django.core.context_processors import csrf
import os
import json

from django.http import JsonResponse
from django.views.generic import TemplateView, View
from django.shortcuts import get_object_or_404, redirect
from django.utils import formats

from reversion import revisions
from preserialize.serialize import serialize

from ledger.accounts.models import EmailUser, Document

from wildlifelicensing.apps.main.mixins import OfficerRequiredMixin, OfficerOrAssessorRequiredMixin
from wildlifelicensing.apps.main.helpers import get_all_officers, render_user_name
from wildlifelicensing.apps.main.serializers import WildlifeLicensingJSONEncoder
from wildlifelicensing.apps.applications.models import Application, AmendmentRequest, Assessment, EmailLogEntry, \
    CustomLogEntry
from wildlifelicensing.apps.applications.forms import IDRequestForm, ReturnsRequestForm, AmendmentRequestForm, \
    ApplicationLogEntryForm
from wildlifelicensing.apps.applications.emails import send_amendment_requested_email, send_assessment_requested_email, \
    send_id_update_request_email, send_returns_request_email, send_assessment_reminder_email
from wildlifelicensing.apps.main.models import AssessorGroup
from wildlifelicensing.apps.returns.models import Return

from wildlifelicensing.apps.applications.utils import PROCESSING_STATUSES, ID_CHECK_STATUSES, RETURNS_CHECK_STATUSES, \
    CHARACTER_CHECK_STATUSES, REVIEW_STATUSES, convert_application_data_files_to_url, format_application, \
    format_amendment_request, format_assessment

APPLICATION_SCHEMA_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))


class ProcessView(OfficerOrAssessorRequiredMixin, TemplateView):
    template_name = 'wl/process/process_app.html'

    def _build_data(self, request, application):
        with open('%s/json/%s.json' % (APPLICATION_SCHEMA_PATH, application.licence_type.code)) as data_file:
            form_structure = json.load(data_file)

        officers = [{'id': officer.id, 'text': render_user_name(officer)} for officer in get_all_officers()]
        officers.insert(0, {'id': 0, 'text': 'Unassigned'})

        current_ass_groups = [ass_request.assessor_group for ass_request in
                              Assessment.objects.filter(application=application)]
        ass_groups = [{'id': ass_group.id, 'text': ass_group.name} for ass_group in
                      AssessorGroup.objects.all().exclude(id__in=[ass_group.pk for ass_group in current_ass_groups])]

        previous_lodgements = []
        for revision in revisions.get_for_object(application).filter(revision__comment='Details Modified').order_by(
                '-revision__date_created'):
            previous_lodgements.append({'lodgement_number': revision.object_version.object.lodgement_number +
                                        '-' + str(revision.object_version.object.lodgement_sequence),
                                        'date': formats.date_format(revision.revision.date_created, 'd/m/Y', True),
                                        'data': revision.object_version.object.data})

        previous_application_returns_outstanding = False
        if application.previous_application is not None:
            previous_application_returns_outstanding = Return.objects.filter(licence=application.previous_application.licence).\
                exclude(status='accepted').exclude(status='submitted').exists()

        convert_application_data_files_to_url(form_structure, application.data, application.documents.all())

        data = {
            'user': serialize(request.user),
            'application': serialize(application, posthook=format_application),
            'form_structure': form_structure,
            'officers': officers,
            'amendment_requests': serialize(AmendmentRequest.objects.filter(application=application),
                                            posthook=format_amendment_request),
            'assessor_groups': ass_groups,
            'assessments': serialize(Assessment.objects.filter(application=application),
                                     posthook=format_assessment),
            'previous_versions': serialize(previous_lodgements),
            'returns_outstanding': previous_application_returns_outstanding,
            'csrf_token': str(csrf(request).get('csrf_token'))
        }

        return data

    def get_context_data(self, **kwargs):
        application = get_object_or_404(Application, pk=self.args[0])
        if 'data' not in kwargs:
            kwargs['data'] = self._build_data(self.request, application)
        kwargs['id_request_form'] = IDRequestForm(application=application, user=self.request.user)
        kwargs['returns_request_form'] = ReturnsRequestForm(application=application, user=self.request.user)
        kwargs['amendment_request_form'] = AmendmentRequestForm(application=application, user=self.request.user)
        kwargs['application_log_entry_form'] = ApplicationLogEntryForm()

        return super(ProcessView, self).get_context_data(**kwargs)

    def post(self, request, *args, **kwargs):
        application = get_object_or_404(Application, pk=self.args[0])
        application.processing_status = 'ready_for_conditions'
        application.save()

        return redirect('applications:enter_conditions', *args, **kwargs)


class AssignOfficerView(OfficerRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        application = get_object_or_404(Application, pk=request.POST['applicationID'])

        try:
            application.assigned_officer = EmailUser.objects.get(pk=request.POST['userID'])
        except EmailUser.DoesNotExist:
            application.assigned_officer = None

        application.processing_status = determine_processing_status(application)
        application.save()

        if application.assigned_officer is not None:
            assigned_officer = {'id': application.assigned_officer.id, 'text': '%s %s' %
                                                                               (application.assigned_officer.first_name,
                                                                                application.assigned_officer.last_name)}
        else:
            assigned_officer = {'id': 0, 'text': 'Unassigned'}

        return JsonResponse({'assigned_officer': assigned_officer,
                             'processing_status': PROCESSING_STATUSES[application.processing_status]},
                            safe=False, encoder=WildlifeLicensingJSONEncoder)


class SetIDCheckStatusView(OfficerRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        application = get_object_or_404(Application, pk=request.POST['applicationID'])
        application.id_check_status = request.POST['status']

        application.customer_status = determine_customer_status(application)
        application.processing_status = determine_processing_status(application)
        application.save()

        return JsonResponse({'id_check_status': ID_CHECK_STATUSES[application.id_check_status],
                             'processing_status': PROCESSING_STATUSES[application.processing_status]},
                            safe=False, encoder=WildlifeLicensingJSONEncoder)


class IDRequestView(OfficerRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        id_request_form = IDRequestForm(request.POST)
        if id_request_form.is_valid():
            id_request = id_request_form.save()

            application = id_request.application
            application.id_check_status = 'awaiting_update'
            application.customer_status = determine_customer_status(application)
            application.processing_status = determine_processing_status(application)
            application.save()
            send_id_update_request_email(id_request, request)

            response = {'id_check_status': ID_CHECK_STATUSES[application.id_check_status],
                        'processing_status': PROCESSING_STATUSES[application.processing_status]}

            return JsonResponse(response, safe=False, encoder=WildlifeLicensingJSONEncoder)
        else:
            return JsonResponse(id_request_form.errors, safe=False, encoder=WildlifeLicensingJSONEncoder)


class ReturnsRequestView(OfficerRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        returns_request_form = ReturnsRequestForm(request.POST)
        if returns_request_form.is_valid():
            returns_request = returns_request_form.save()

            application = returns_request.application
            application.returns_check_status = 'awaiting_returns'
            application.customer_status = determine_customer_status(application)
            application.processing_status = determine_processing_status(application)
            application.save()
            send_returns_request_email(returns_request, request)

            response = {'returns_check_status': RETURNS_CHECK_STATUSES[application.returns_check_status],
                        'processing_status': PROCESSING_STATUSES[application.processing_status]}

            return JsonResponse(response, safe=False, encoder=WildlifeLicensingJSONEncoder)
        else:
            return JsonResponse(returns_request_form.errors, safe=False, encoder=WildlifeLicensingJSONEncoder)


class SetReturnsCheckStatusView(OfficerRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        application = get_object_or_404(Application, pk=request.POST['applicationID'])
        application.returns_check_status = request.POST['status']

        application.customer_status = determine_customer_status(application)
        application.processing_status = determine_processing_status(application)
        application.save()

        return JsonResponse({'returns_check_status': CHARACTER_CHECK_STATUSES[application.returns_check_status],
                             'processing_status': PROCESSING_STATUSES[application.processing_status]},
                            safe=False, encoder=WildlifeLicensingJSONEncoder)


class SetCharacterCheckStatusView(OfficerRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        application = get_object_or_404(Application, pk=request.POST['applicationID'])
        application.character_check_status = request.POST['status']

        application.processing_status = determine_processing_status(application)
        application.save()

        return JsonResponse({'character_check_status': CHARACTER_CHECK_STATUSES[application.character_check_status],
                             'processing_status': PROCESSING_STATUSES[application.processing_status]},
                            safe=False, encoder=WildlifeLicensingJSONEncoder)


class SetReviewStatusView(OfficerRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        application = get_object_or_404(Application, pk=request.POST['applicationID'])
        application.review_status = request.POST['status']

        application.customer_status = determine_customer_status(application)
        application.processing_status = determine_processing_status(application)
        application.save()

        response = {'review_status': REVIEW_STATUSES[application.review_status],
                    'processing_status': PROCESSING_STATUSES[application.processing_status]}

        return JsonResponse(response, safe=False, encoder=WildlifeLicensingJSONEncoder)


class AmendmentRequestView(OfficerRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        amendment_request_form = AmendmentRequestForm(request.POST)
        if amendment_request_form.is_valid():
            amendment_request = amendment_request_form.save()

            application = amendment_request.application
            application.review_status = 'awaiting_amendments'
            application.customer_status = determine_customer_status(application)
            application.processing_status = determine_processing_status(application)
            application.save()

            send_amendment_requested_email(application, amendment_request, request=request)

            response = {'review_status': REVIEW_STATUSES[application.review_status],
                        'processing_status': PROCESSING_STATUSES[application.processing_status],
                        'amendment_request': serialize(amendment_request, posthook=format_amendment_request)}

            return JsonResponse(response, safe=False, encoder=WildlifeLicensingJSONEncoder)
        else:
            return JsonResponse(amendment_request_form.errors, safe=False, encoder=WildlifeLicensingJSONEncoder)


class SendForAssessmentView(OfficerRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        application = get_object_or_404(Application, pk=request.POST['applicationID'])

        ass_group = get_object_or_404(AssessorGroup, pk=request.POST['assGroupID'])
        assessment = Assessment.objects.create(application=application, assessor_group=ass_group,
                                               status=request.POST['status'], user=request.user)

        application.processing_status = determine_processing_status(application)
        application.save()
        send_assessment_requested_email(assessment, request)

        return JsonResponse({'assessment': serialize(assessment, posthook=format_assessment),
                             'processing_status': PROCESSING_STATUSES[application.processing_status]},
                            safe=False, encoder=WildlifeLicensingJSONEncoder)


class RemindAssessmentView(OfficerRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        assessment = get_object_or_404(Assessment, pk=request.POST['assessmentID'])

        send_assessment_reminder_email(assessment, request)

        return JsonResponse('ok', safe=False, encoder=WildlifeLicensingJSONEncoder)


def determine_processing_status(application):
    status = 'ready_for_action'

    if application.id_check_status == 'awaiting_update' or application.review_status == 'awaiting_amendments':
        status = 'awaiting_applicant_response'

    if Assessment.objects.filter(application=application).filter(status='awaiting_assessment').exists():
        if status == 'awaiting_applicant_response':
            status = 'awaiting_responses'
        else:
            status = 'awaiting_assessor_response'

    return status


def determine_customer_status(application):
    status = 'under_review'

    if application.id_check_status == 'awaiting_update':
        if application.returns_check_status == 'awaiting_returns':
            if application.review_status == 'awaiting_amendments':
                status = 'id_and_returns_and_amendment_required'
            else:
                status = 'id_and_returns_required'
        elif application.review_status == 'awaiting_amendments':
            status = 'id_and_amendment_required'
        else:
            status = 'id_required'
    elif application.returns_check_status == 'awaiting_returns':
        if application.review_status == 'awaiting_amendments':
            status = 'returns_and_amendments_required'
        else:
            status = 'returns_required'
    elif application.review_status == 'awaiting_amendments':
        status = 'amendment_required'

    return status


class CommunicationLogListView(OfficerRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        application = get_object_or_404(Application, pk=args[0])
        data = []
        for obj in EmailLogEntry.objects.filter(application=application):
            r = {
                'date': obj.created,
                'type': 'Email',
                'subject': obj.subject,
                'text': obj.text,
                'document': obj.document.file.url if obj.document else None
            }
            data.append(r)

        for obj in CustomLogEntry.objects.filter(application=application):
            r = {
                'date': obj.created,
                'type': 'Custom',
                'subject': obj.subject,
                'text': obj.text,
                'document': obj.document.file.url if obj.document else None
            }
            data.append(r)

        return JsonResponse({'data': data}, safe=False, encoder=WildlifeLicensingJSONEncoder)


class AddLogEntryView(OfficerRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        form = ApplicationLogEntryForm(data=request.POST, files=request.FILES)
        if form.is_valid():
            application = get_object_or_404(Application, pk=args[0])
            user = request.user
            document = None
            if request.FILES and 'document' in request.FILES:
                document = Document.objects.create(file=request.FILES['document'])
            data = {
                'document': document,
                'user': user,
                'application': application,
                'text': form.cleaned_data['text'],
                'subject': form.cleaned_data['subject']
            }
            entry = CustomLogEntry.objects.create(**data)
            return JsonResponse('ok', safe=False, encoder=WildlifeLicensingJSONEncoder)
        else:
            return JsonResponse(
                {
                    "errors": [
                        {
                            'status': "422",
                            'title': 'Data not valid',
                            'detail': form.errors
                        }
                    ]
                },
                safe=False, encoder=WildlifeLicensingJSONEncoder, status_code=422)
