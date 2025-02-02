"""Integration checks that run daily (via Github action) between client and prod server."""
import os

import numpy as np
import pytest
import qiskit
from applications_superstaq import SuperstaQException

import qiskit_superstaq


@pytest.fixture
def provider() -> qiskit_superstaq.superstaq_provider.SuperstaQProvider:
    token = os.environ["TEST_USER_TOKEN"]
    provider = qiskit_superstaq.superstaq_provider.SuperstaQProvider(api_key=token)
    return provider


def test_backends() -> None:
    token = os.environ["TEST_USER_TOKEN"]
    provider = qiskit_superstaq.superstaq_provider.SuperstaQProvider(api_key=token)
    result = provider.backends()
    assert provider.get_backend("ibmq_qasm_simulator") in result
    assert provider.get_backend("aqt_keysight_qpu") in result


def test_ibmq_set_token() -> None:
    api_token = os.environ["TEST_USER_TOKEN"]
    ibmq_token = os.environ["TEST_USER_IBMQ_TOKEN"]
    provider = qiskit_superstaq.superstaq_provider.SuperstaQProvider(api_key=api_token)
    assert provider.ibmq_set_token(ibmq_token) == "Your IBMQ account token has been updated"

    with pytest.raises(SuperstaQException, match="IBMQ token is invalid."):
        assert provider.ibmq_set_token("INVALID_TOKEN")


def test_ibmq_compile(provider: qiskit_superstaq.superstaq_provider.SuperstaQProvider) -> None:
    qc = qiskit.QuantumCircuit(2)
    qc.append(qiskit_superstaq.AceCR("+-"), [0, 1])
    out = provider.ibmq_compile(qc, target="ibmq_jakarta_qpu")
    assert isinstance(out, qiskit_superstaq.compiler_output.CompilerOutput)
    assert isinstance(out.circuit, qiskit.QuantumCircuit)
    assert isinstance(out.pulse_sequence, qiskit.pulse.Schedule)
    assert 800 <= out.pulse_sequence.duration <= 1000  # 896 as of 12/27/2021
    assert out.pulse_sequence.start_time == 0
    assert len(out.pulse_sequence) == 5


def test_acer_non_neighbor_qubits_compile(
    provider: qiskit_superstaq.superstaq_provider.SuperstaQProvider,
) -> None:
    qc = qiskit.QuantumCircuit(4)
    qc.append(qiskit_superstaq.AceCR("-+"), [0, 1])
    qc.append(qiskit_superstaq.AceCR("-+"), [1, 2])
    qc.append(qiskit_superstaq.AceCR("-+"), [2, 3])
    out = provider.ibmq_compile(qc, target="ibmq_bogota_qpu")
    assert isinstance(out, qiskit_superstaq.compiler_output.CompilerOutput)
    assert isinstance(out.circuit, qiskit.QuantumCircuit)
    assert isinstance(out.pulse_sequence, qiskit.pulse.Schedule)
    assert 5700 <= out.pulse_sequence.duration <= 7500  # 7424 as of 4/06/2022
    assert out.pulse_sequence.start_time == 0
    assert len(out.pulse_sequence) == 67


def test_aqt_compile(provider: qiskit_superstaq.superstaq_provider.SuperstaQProvider) -> None:
    circuit = qiskit.QuantumCircuit(8)
    circuit.h(4)
    expected = qiskit.QuantumCircuit(5)
    expected.rz(np.pi / 2, 4)
    expected.rx(np.pi / 2, 4)
    expected.rz(np.pi / 2, 4)
    assert provider.aqt_compile(circuit).circuit == expected
    assert provider.aqt_compile([circuit]).circuits == [expected]
    assert provider.aqt_compile([circuit, circuit]).circuits == [expected, expected]


def test_get_balance(provider: qiskit_superstaq.superstaq_provider.SuperstaQProvider) -> None:
    balance_str = provider.get_balance()
    assert isinstance(balance_str, str)
    assert balance_str.startswith("$")

    assert isinstance(provider.get_balance(pretty_output=False), float)


def test_qscout_compile(provider: qiskit_superstaq.superstaq_provider.SuperstaQProvider) -> None:
    circuit = qiskit.QuantumCircuit(1)
    circuit.h(0)
    expected = qiskit.QuantumCircuit(1)
    expected.u(-np.pi / 2, 0, 0, 0)
    expected.z(0)
    assert provider.qscout_compile(circuit).circuit == expected
    assert provider.qscout_compile([circuit]).circuits == [expected]
    assert provider.qscout_compile([circuit, circuit]).circuits == [expected, expected]


def test_cq_compile(provider: qiskit_superstaq.superstaq_provider.SuperstaQProvider) -> None:
    from qiskit.circuit.library import GR

    circuit = qiskit.QuantumCircuit(1)
    circuit.h(0)
    expected = qiskit.QuantumCircuit(1)
    expected.append(GR(1, -0.25 * np.pi, 0.5 * np.pi), [0])
    expected.z(0)
    expected.append(GR(1, 0.25 * np.pi, 0.5 * np.pi), [0])
    assert provider.cq_compile(circuit).circuit == expected
    assert provider.cq_compile([circuit]).circuits == [expected]
    assert provider.cq_compile([circuit, circuit]).circuits == [expected, expected]


def test_get_aqt_configs(provider: qiskit_superstaq.superstaq_provider.SuperstaQProvider) -> None:
    res = provider.aqt_get_configs()
    assert "pulses" in res
    assert "variables" in res
