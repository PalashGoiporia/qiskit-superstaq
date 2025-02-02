import os
import textwrap
from unittest import mock
from unittest.mock import MagicMock, patch

import applications_superstaq
import pytest
import qiskit

import qiskit_superstaq as qss


@patch.dict(os.environ, {"SUPERSTAQ_API_KEY": ""})
def test_provider() -> None:
    ss_provider = qss.superstaq_provider.SuperstaQProvider(api_key="MY_TOKEN")

    with pytest.raises(EnvironmentError, match="api_key was not "):
        qss.superstaq_provider.SuperstaQProvider()

    assert str(ss_provider.get_backend("ibmq_qasm_simulator")) == str(
        qss.superstaq_backend.SuperstaQBackend(
            provider=ss_provider,
            remote_host=qss.API_URL,
            backend="ibmq_qasm_simulator",
        )
    )

    assert str(ss_provider) == "<SuperstaQProvider(name=superstaq_provider)>"

    assert repr(ss_provider) == "<SuperstaQProvider(name=superstaq_provider, api_key=MY_TOKEN)>"

    backends = {
        "superstaq_backends": {
            "compile-and-run": [
                "ibmq_qasm_simulator",
                "ibmq_armonk_qpu",
                "ibmq_santiago_qpu",
                "ibmq_bogota_qpu",
                "ibmq_lima_qpu",
                "ibmq_belem_qpu",
                "ibmq_quito_qpu",
                "ibmq_statevector_simulator",
                "ibmq_mps_simulator",
                "ibmq_extended-stabilizer_simulator",
                "ibmq_stabilizer_simulator",
                "ibmq_manila_qpu",
                "d-wave_advantage-system1.1_qpu",
                "aws_dm1_simulator",
                "aws_tn1_simulator",
                "ionq_ion_qpu",
                "d-wave_dw-2000q-6_qpu",
                "d-wave_advantage-system4.1_qpu",
                "aws_sv1_simulator",
                "rigetti_aspen-9_qpu",
            ],
            "compile-only": ["aqt_keysight_qpu", "sandia_qscout_qpu"],
        }
    }
    backend_names = backends["superstaq_backends"]["compile-and-run"]

    expected_backends = []
    for name in backend_names:
        expected_backends.append(
            qss.superstaq_backend.SuperstaQBackend(
                provider=ss_provider, remote_host=qss.API_URL, backend=name
            )
        )

    mock_client = MagicMock()
    mock_client.get_backends.return_value = backends
    ss_provider._client = mock_client
    assert ss_provider.backends() == expected_backends


@patch.dict(os.environ, {"SUPERSTAQ_API_KEY": ""})
def test_get_balance() -> None:
    ss_provider = qss.superstaq_provider.SuperstaQProvider(api_key="MY_TOKEN")
    mock_client = MagicMock()
    mock_client.get_balance.return_value = {"balance": 12345.6789}
    ss_provider._client = mock_client

    assert ss_provider.get_balance() == "$12,345.68"
    assert ss_provider.get_balance(pretty_output=False) == 12345.6789


@patch("requests.post")
def test_aqt_compile(mock_post: MagicMock) -> None:
    provider = qss.superstaq_provider.SuperstaQProvider(api_key="MY_TOKEN")

    qc = qiskit.QuantumCircuit(8)
    qc.cz(4, 5)

    mock_post.return_value.json = lambda: {
        "qiskit_circuits": qss.serialization.serialize_circuits(qc),
        "state_jp": applications_superstaq.converters.serialize({}),
        "pulse_lists_jp": applications_superstaq.converters.serialize([[[]]]),
    }
    out = provider.aqt_compile(qc)
    assert out.circuit == qc
    assert not hasattr(out, "circuits") and not hasattr(out, "pulse_lists")

    out = provider.aqt_compile([qc])
    assert out.circuits == [qc]
    assert not hasattr(out, "circuit") and not hasattr(out, "pulse_list")

    mock_post.return_value.json = lambda: {
        "qiskit_circuits": qss.serialization.serialize_circuits([qc, qc]),
        "state_jp": applications_superstaq.converters.serialize({}),
        "pulse_lists_jp": applications_superstaq.converters.serialize([[[]], [[]]]),
    }
    out = provider.aqt_compile([qc, qc])
    assert out.circuits == [qc, qc]
    assert not hasattr(out, "circuit") and not hasattr(out, "pulse_list")


@patch("requests.post")
def test_service_aqt_compile_eca(mock_post: MagicMock) -> None:
    provider = qss.superstaq_provider.SuperstaQProvider(api_key="MY_TOKEN")

    qc = qiskit.QuantumCircuit(8)
    qc.cz(4, 5)

    mock_post.return_value.json = lambda: {
        "qiskit_circuits": qss.serialization.serialize_circuits(qc),
        "state_jp": applications_superstaq.converters.serialize({}),
        "pulse_lists_jp": applications_superstaq.converters.serialize([[[]]]),
    }

    out = provider.aqt_compile_eca(qc, num_equivalent_circuits=1, random_seed=1234)
    assert out.circuits == [qc]
    assert not hasattr(out, "circuit") and not hasattr(out, "pulse_list")


@patch(
    "applications_superstaq.superstaq_client._SuperstaQClient.ibmq_compile",
)
def test_service_ibmq_compile(mock_ibmq_compile: MagicMock) -> None:
    provider = qss.superstaq_provider.SuperstaQProvider(api_key="MY_TOKEN")
    qc = qiskit.QuantumCircuit(8)
    qc.cz(4, 5)
    mock_ibmq_compile.return_value = {
        "qiskit_circuits": qss.serialization.serialize_circuits(qc),
        "pulses": applications_superstaq.converters.serialize([mock.DEFAULT]),
    }

    assert provider.ibmq_compile(qiskit.QuantumCircuit()) == qss.compiler_output.CompilerOutput(
        qc, mock.DEFAULT, None, None, None
    )
    assert provider.ibmq_compile([qiskit.QuantumCircuit()]) == qss.compiler_output.CompilerOutput(
        [qc], [mock.DEFAULT], None, None, None
    )


@patch("requests.post")
def test_qscout_compile(mock_post: MagicMock) -> None:
    provider = qss.superstaq_provider.SuperstaQProvider(api_key="MY_TOKEN")

    qc = qiskit.QuantumCircuit(1)
    qc.h(0)

    jaqal_program = textwrap.dedent(
        """\
        register allqubits[1]

        prepare_all
        R allqubits[0] -1.5707963267948966 1.5707963267948966
        Rz allqubits[0] -3.141592653589793
        measure_all
        """
    )

    mock_post.return_value.json = lambda: {
        "qiskit_circuits": qss.serialization.serialize_circuits(qc),
        "jaqal_programs": [jaqal_program],
    }
    out = provider.qscout_compile(qc)
    assert out.circuit == qc

    out = provider.qscout_compile([qc])
    assert out.circuits == [qc]

    mock_post.return_value.json = lambda: {
        "qiskit_circuits": qss.serialization.serialize_circuits([qc, qc]),
        "jaqal_programs": [jaqal_program, jaqal_program],
    }
    out = provider.qscout_compile([qc, qc])
    assert out.circuits == [qc, qc]


@patch("requests.post")
def test_cq_compile(mock_post: MagicMock) -> None:
    provider = qss.superstaq_provider.SuperstaQProvider(api_key="MY_TOKEN")

    qc = qiskit.QuantumCircuit(1)
    qc.h(0)

    mock_post.return_value.json = lambda: {
        "qiskit_circuits": qss.serialization.serialize_circuits(qc)
    }
    out = provider.cq_compile(qc)
    assert out.circuit == qc

    out = provider.cq_compile([qc])
    assert out.circuits == [qc]

    mock_post.return_value.json = lambda: {
        "qiskit_circuits": qss.serialization.serialize_circuits([qc, qc])
    }
    out = provider.cq_compile([qc, qc])
    assert out.circuits == [qc, qc]


@patch(
    "applications_superstaq.superstaq_client._SuperstaQClient.neutral_atom_compile",
    return_value={"pulses": applications_superstaq.converters.serialize([mock.DEFAULT])},
)
def test_neutral_atom_compile(mock_ibmq_compile: MagicMock) -> None:
    provider = qss.superstaq_provider.SuperstaQProvider(api_key="MY_TOKEN")
    assert provider.neutral_atom_compile(qiskit.QuantumCircuit()) == mock.DEFAULT
    assert provider.neutral_atom_compile([qiskit.QuantumCircuit()]) == [mock.DEFAULT]

    with mock.patch.dict("sys.modules", {"unittest": None}), pytest.raises(
        applications_superstaq.SuperstaQModuleNotFoundException,
        match="'neutral_atom_compile' requires module 'unittest'",
    ):
        _ = provider.neutral_atom_compile(qiskit.QuantumCircuit())
