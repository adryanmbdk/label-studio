"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

import logging
import os
import urllib

import requests
from core.feature_flags import flag_set
from core.utils.common import load_func
from core.version import get_git_version
from data_export.serializers import ExportDataSerializer
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.db.models import Count
from requests.adapters import HTTPAdapter
from requests.auth import HTTPBasicAuth

from label_studio.core.utils.params import get_env

version = get_git_version()
logger = logging.getLogger(__name__)

CONNECTION_TIMEOUT = float(get_env('ML_CONNECTION_TIMEOUT', 1))  # seconds
TIMEOUT_DEFAULT = float(get_env('ML_TIMEOUT_DEFAULT', 100))  # seconds

TIMEOUT_TRAIN = float(get_env('ML_TIMEOUT_TRAIN', 30))
TIMEOUT_PREDICT = float(get_env('ML_TIMEOUT_PREDICT', 100))
TIMEOUT_HEALTH = float(get_env('ML_TIMEOUT_HEALTH', 1))
TIMEOUT_SETUP = float(get_env('ML_TIMEOUT_SETUP', 3))
TIMEOUT_DUPLICATE_MODEL = float(get_env('ML_TIMEOUT_DUPLICATE_MODEL', 1))
TIMEOUT_DELETE = float(get_env('ML_TIMEOUT_DELETE', 1))
TIMEOUT_TRAIN_JOB_STATUS = float(get_env('ML_TIMEOUT_TRAIN_JOB_STATUS', 1))

# TODO
# we would need to make it configurable on the ML backend side too
PREDICT_URL = 'predict'
HEALTH_URL = 'health'
VALIDATE_URL = 'validate'
SETUP_URL = 'setup'
DUPLICATE_URL = 'duplicate_model'
DELETE_URL = 'delete'
JOB_STATUS_URL = 'job_status'
VERSIONS_URL = 'versions'


def get_ml_backend_hostname() -> str:
    """
    [Smell 1 corrigido - Duplicated Code]
    Antes esta expressao estava repetida em 3 metodos (train,
    _prep_prediction_req, setup). Centralizada aqui = fonte unica de verdade.
    """
    return settings.HOSTNAME if settings.HOSTNAME else f'http://localhost:{settings.INTERNAL_PORT}'

def create_project_uid(project) -> str:
    """Gera o identificador unico do projeto usado nas requisicoes ao ML backend."""
    time_id = int(project.created_at.timestamp())
    return f'{project.id}.{time_id}'

class MLRequestPayloadBuilder:
    """
    [Padrao Builder]
    Monta de forma incremental os payloads enviados ao ML backend.
    Resolve o Smell 2: antes cada metodo de MLApi montava seu proprio
    dict repetindo chaves como 'project', 'label_config' e 'hostname'.
    """

    def __init__(self, ml_api: 'MLApi'):
        self._ml_api = ml_api
        self._payload = {}

    def with_project(self, project) -> 'MLRequestPayloadBuilder':
        self._payload['project'] = create_project_uid(project)
        return self

    def with_label_config(self, project) -> 'MLRequestPayloadBuilder':
        self._payload['label_config'] = project.label_config
        return self

    def with_hostname(self) -> 'MLRequestPayloadBuilder':
        self._payload['hostname'] = get_ml_backend_hostname()
        return self

    def with_params(self, **params) -> 'MLRequestPayloadBuilder':
        self._payload['params'] = params
        return self

    def with_extra(self, **kwargs) -> 'MLRequestPayloadBuilder':
        self._payload.update(kwargs)
        return self

    def build(self) -> dict:
        return dict(self._payload)


class BaseHTTPAPI(object):
    MAX_RETRIES = 2
    HEADERS = {
        'User-Agent': 'heartex/' + (version or ''),
    }

    def __init__(
        self, url, timeout=None, connection_timeout=None, max_retries=None, headers=None, auth_method=None, **kwargs
    ):
        self._url = url
        self._timeout = timeout or TIMEOUT_DEFAULT
        self._connection_timeout = connection_timeout or CONNECTION_TIMEOUT
        self._headers = headers or {}
        self._auth_method = auth_method

        # TODO basic auth parameters must be required for auth_method == 'basic'
        self._basic_auth = (kwargs.get('basic_auth_user'), kwargs.get('basic_auth_pass'))

        self._max_retries = max_retries or self.MAX_RETRIES
        self._sessions = {self._session_key(): self.create_session()}

    def create_session(self):
        session = requests.Session()
        session.headers.update(self.HEADERS)
        session.headers.update(self._headers)
        session.mount('http://', HTTPAdapter(max_retries=self._max_retries))
        session.mount('https://', HTTPAdapter(max_retries=self._max_retries))
        return session

    def _session_key(self):
        return os.getpid()

    @property
    def http(self):
        key = self._session_key()
        if key in self._sessions:
            return self._sessions[key]
        else:
            session = self.create_session()
            self._sessions[key] = session
            return session

    def _apply_timeout(self, kwargs):
        """[Smell 3 corrigido - parte 1] Unica responsabilidade: resolver o timeout."""
        if 'timeout' not in kwargs:
            kwargs['timeout'] = self._connection_timeout, self._timeout
        elif isinstance(kwargs['timeout'], (float, int)):
            kwargs['timeout'] = (self._connection_timeout, kwargs['timeout'])

    def _apply_auth(self, kwargs):
        """[Smell 3 corrigido - parte 2] Unica responsabilidade: injetar auth basica."""
        if self._basic_auth[0] and self._basic_auth[1]:
            kwargs['auth'] = HTTPBasicAuth(*self._basic_auth)

    def _prepare_kwargs(self, kwargs):
        self._apply_auth(kwargs)
        self._apply_timeout(kwargs)

    def request(self, method, *args, **kwargs):
        self._prepare_kwargs(kwargs)
        return self.http.request(method, *args, **kwargs)

    def get(self, *args, **kwargs):
        return self.request('GET', *args, **kwargs)

    def post(self, *args, **kwargs):
        return self.request('POST', *args, **kwargs)


class MLApiResult:
    """
    Class for storing the result of ML API request
    """

    def __init__(self, url='', request='', response=None, headers=None, type='ok', status_code=200):
        self.url = url
        self.request = request
        self.response = {} if response is None else response
        self.headers = {} if headers is None else headers
        self.type = type
        self.status_code = status_code

    @property
    def is_error(self):
        return self.type == 'error'

    @property
    def error_message(self):
        return self.response.get('error')


class MLApi(BaseHTTPAPI):
    """
    [Padrao Facade]
    Expoe uma interface simples (train, make_predictions, health, setup,
    delete...) escondendo a complexidade de sessoes HTTP, retries e
    timeouts (BaseHTTPAPI) e a montagem de payload (MLRequestPayloadBuilder).
    """

    def __init__(self, **kwargs):
        super(MLApi, self).__init__(**kwargs)
        self._validate_request_timeout = 10

    def _payload_builder(self) -> MLRequestPayloadBuilder:
        return MLRequestPayloadBuilder(self)

    def _get_url(self, url_suffix):
        url = self._url
        if url[-1] != '/':
            url += '/'
        return urllib.parse.urljoin(url, url_suffix)

    def _request(self, url_suffix, request=None, verbose=True, method='POST', *args, **kwargs):
        assert method in ('POST', 'GET')
        url = self._get_url(url_suffix)
        request = request or {}
        headers = dict(self.http.headers)

        response = None
        try:
            if method == 'POST':
                response = self.post(url=url, json=request, *args, **kwargs)
            else:
                response = self.get(url=url, *args, **kwargs)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            error_string = str(e)
            status_code = response.status_code if response is not None else 0
            return MLApiResult(url, request, {'error': error_string}, headers, 'error', status_code=status_code)
        status_code = response.status_code
        try:
            response = response.json()
        except ValueError as e:
            return MLApiResult(
                url=url,
                request=request,
                response={'error': str(e), 'response': response.content},
                headers=headers,
                type='error',
                status_code=status_code,
            )

        return MLApiResult(url=url, request=request, response=response, headers=headers, status_code=status_code)

    def train(self, project, use_ground_truth=False):
        # TODO Replace AnonymousUser with real user from request
        user = AnonymousUser()
        # Identify if feature flag is turned on
        if flag_set('ff_back_dev_1417_start_training_mlbackend_webhooks_250122_long', user):
            request = {
                'action': 'START_TRAINING',
                'project': load_func(settings.WEBHOOK_SERIALIZERS['project'])(instance=project).data,
            }
            return self._request('webhook', request, verbose=False, timeout=TIMEOUT_PREDICT)

        # get only tasks with annotations
        tasks = project.tasks.annotate(num_annotations=Count('annotations')).filter(num_annotations__gt=0)
        # create serialized tasks with annotations: {"data": {...}, "annotations": [{...}], "predictions": [{...}]}
        tasks_ser = ExportDataSerializer(tasks, many=True).data
        logger.debug(f'{len(tasks_ser)} tasks with annotations are sent to ML backend for training.')

        request = (
            self._payload_builder()
            .with_extra(annotations=tasks_ser)
            .with_project(project)
            .with_label_config(project)
            .with_hostname()
            .with_params(login=project.task_data_login, password=project.task_data_password)
            .build()
        )
        return self._request('train', request, verbose=False, timeout=TIMEOUT_PREDICT)

    def _prep_prediction_req(self, tasks, project, context=None):
        return (
            self._payload_builder()
            .with_extra(tasks=tasks)
            .with_project(project)
            .with_label_config(project)
            .with_params(
                login=project.task_data_login,
                password=project.task_data_password,
                hostname=get_ml_backend_hostname(),
                context=context,
            )
            .build()
        )

    def make_predictions(self, tasks, project, context=None):
        request = self._prep_prediction_req(tasks, project, context=context)
        return self._request(PREDICT_URL, request, verbose=False, timeout=TIMEOUT_PREDICT)

    def health(self):
        return self._request(HEALTH_URL, method='GET', timeout=TIMEOUT_HEALTH)

    def validate(self, config):
        return self._request(VALIDATE_URL, request={'config': config}, timeout=self._validate_request_timeout)

    def setup(self, project, extra_params=None, **kwargs):
        request = (
            self._payload_builder()
            .with_project(project)
            .with_hostname()
            .with_extra(
                schema=project.label_config,
                access_token=project.created_by.auth_token.key,
                extra_params=extra_params,
            )
            .build()
        )
        return self._request(SETUP_URL, request=request, timeout=TIMEOUT_SETUP)

    def duplicate_model(self, project_src, project_dst):
        return self._request(
            DUPLICATE_URL,
            request={
                'project_src': create_project_uid(project_src),
                'project_dst': create_project_uid(project_dst),
            },
            timeout=TIMEOUT_DUPLICATE_MODEL,
        )

    def delete(self, project):
        return self._request(
            DELETE_URL, request={'project': create_project_uid(project)}, timeout=TIMEOUT_DELETE
        )

    def get_train_job_status(self, train_job):
        return self._request(JOB_STATUS_URL, request={'job': train_job.job_id}, timeout=TIMEOUT_TRAIN_JOB_STATUS)

    def get_versions(self, project):
        return self._request(
            VERSIONS_URL, request={'project': create_project_uid(project)}, timeout=TIMEOUT_SETUP, method='GET'
        )


def get_ml_api(project):
    if project.ml_backend_active_connection is None:
        return None
    if project.ml_backend_active_connection.ml_backend is None:
        return None
    return MLApi(
        url=project.ml_backend_active_connection.ml_backend.url,
        timeout=project.ml_backend_active_connection.ml_backend.timeout,
    )
