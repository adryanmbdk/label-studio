"""Testes unitários para a refatoração do ml/api_connector.py (Caminho B)."""
from unittest.mock import Mock

from django.test import override_settings
from ml.api_connector import (
    MLRequestPayloadBuilder,
    create_project_uid,
    get_ml_backend_hostname,
)


@override_settings(HOSTNAME='https://meudominio.com')
def test_hostname_usa_settings_quando_definido():
    """Smell 1: a resolucao de hostname agora tem fonte unica de verdade."""
    assert get_ml_backend_hostname() == 'https://meudominio.com'


@override_settings(HOSTNAME='', INTERNAL_PORT='8080')
def test_hostname_usa_localhost_quando_nao_definido():
    """Smell 1: fallback para localhost preserva o comportamento original."""
    assert get_ml_backend_hostname() == 'http://localhost:8080'


def test_builder_monta_payload_incrementalmente():
    """Padrao Builder: payload montado por composicao, sem duplicacao."""
    ml_api = Mock()
    project = Mock(label_config='<View></View>')
    project.id = 7
    project.created_at.timestamp.return_value = 1700000000

    payload = (
        MLRequestPayloadBuilder(ml_api)
        .with_project(project)
        .with_label_config(project)
        .with_params(login='user', password='pass')
        .build()
    )

    assert payload == {
        'project': '7.1700000000',
        'label_config': '<View></View>',
        'params': {'login': 'user', 'password': 'pass'},
    }


def test_builder_nao_compartilha_estado_entre_instancias():
    """Padrao Builder: cada instancia tem payload isolado (evita mutacao compartilhada)."""
    ml_api = Mock()
    project = Mock(label_config='cfg')
    project.id = 1
    project.created_at.timestamp.return_value = 1700000000

    MLRequestPayloadBuilder(ml_api).with_project(project)
    builder2 = MLRequestPayloadBuilder(ml_api)

    assert builder2.build() == {}


def test_create_project_uid_formata_id_e_timestamp():
    """Funcao extraida da classe: nao depende de estado de MLApi."""
    project = Mock()
    project.id = 42
    project.created_at.timestamp.return_value = 1699999999.7

    assert create_project_uid(project) == '42.1699999999'