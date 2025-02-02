# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2021.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

import os
from typing import List, Optional, Union

import applications_superstaq
import qiskit
from applications_superstaq import finance
from applications_superstaq import logistics
from applications_superstaq import superstaq_client
from applications_superstaq import user_config

import qiskit_superstaq as qss


class SuperstaQProvider(
    qiskit.providers.ProviderV1, finance.Finance, logistics.Logistics, user_config.UserConfig
):
    """Provider for SuperstaQ backend.

    Typical usage is:

    .. code-block:: python

        import qiskit_superstaq as qss

        ss_provider = qss.superstaq_provider.SuperstaQProvider('MY_TOKEN')

        backend = ss_provider.get_backend('my_backend')

    where `'MY_TOKEN'` is the access token provided by SuperstaQ,
    and 'my_backend' is the name of the desired backend.

    Args:
         Args:
            remote_host: The location of the API in the form of a URL. If this is None,
                then this instance will use the environment variable `SUPERSTAQ_REMOTE_HOST`.
                If that variable is not set, then this uses
                `https://superstaq.super.tech/{api_version}`,
                where `{api_version}` is the `api_version` specified below.
            api_key: A string key which allows access to the API. If this is None,
                then this instance will use the environment variable  `SUPERSTAQ_API_KEY`. If that
                variable is not set, then this will raise an `EnvironmentError`.
            default_target: Which target to default to using. If set to None, no default is set
                and target must always be specified in calls. If set, then this default is used,
                unless a target is specified for a given call. Supports either 'qpu' or
                'simulator'.
            api_version: Version of the API.
            max_retry_seconds: The number of seconds to retry calls for. Defaults to one hour.
            verbose: Whether to print to stdio and stderr on retriable errors.
        Raises:
            EnvironmentError: if the `api_key` is None and has no corresponding environment
                variable set.
    """

    def __init__(
        self,
        remote_host: Optional[str] = None,
        api_key: Optional[str] = None,
        default_target: str = None,
        api_version: str = applications_superstaq.API_VERSION,
        max_retry_seconds: int = 3600,
        verbose: bool = False,
    ) -> None:
        self._name = "superstaq_provider"
        self.remote_host = (
            remote_host or os.getenv("SUPERSTAQ_REMOTE_HOST") or applications_superstaq.API_URL
        )
        self.api_key = api_key or os.getenv("SUPERSTAQ_API_KEY")
        if not self.api_key:
            raise EnvironmentError(
                "Parameter api_key was not specified and the environment variable "
                "SUPERSTAQ_API_KEY was also not set."
            )

        self._client = superstaq_client._SuperstaQClient(
            client_name="qiskit-superstaq",
            remote_host=self.remote_host,
            api_key=self.api_key,
            default_target=default_target,
            api_version=api_version,
            max_retry_seconds=max_retry_seconds,
            verbose=verbose,
        )

    def __str__(self) -> str:
        return f"<SuperstaQProvider(name={self._name})>"

    def __repr__(self) -> str:
        repr1 = f"<SuperstaQProvider(name={self._name}, "
        return repr1 + f"api_key={self.api_key})>"

    def get_backend(self, backend: str) -> "qss.superstaq_backend.SuperstaQBackend":
        return qss.superstaq_backend.SuperstaQBackend(
            provider=self, remote_host=self.remote_host, backend=backend
        )

    def get_access_token(self) -> Optional[str]:
        return self.api_key

    def backends(self) -> List[qss.superstaq_backend.SuperstaQBackend]:
        ss_backends = self._client.get_backends()["superstaq_backends"]
        backends = []
        for backend_str in ss_backends["compile-and-run"]:
            backends.append(self.get_backend(backend_str))
        return backends

    def _http_headers(self) -> dict:
        return {
            "Authorization": self.get_access_token(),
            "Content-Type": "application/json",
            "X-Client-Name": "qiskit-superstaq",
            "X-Client-Version": qss.API_VERSION,
        }

    def aqt_compile(
        self,
        circuits: Union[qiskit.QuantumCircuit, List[qiskit.QuantumCircuit]],
        target: str = "keysight",
    ) -> "qss.compiler_output.CompilerOutput":
        """Compiles the given circuit(s) to AQT device, optimized to its native gate set.

        Args:
            circuits: qiskit QuantumCircuit(s)
        Returns:
            object whose .circuit(s) attribute is an optimized qiskit QuantumCircuit(s)
            If qtrl is installed, the object's .seq attribute is a qtrl Sequence object of the
            pulse sequence corresponding to the optimized qiskit.QuantumCircuit(s) and the
            .pulse_list(s) attribute is the list(s) of cycles.
        """
        serialized_circuits = qss.serialization.serialize_circuits(circuits)
        circuits_is_list = not isinstance(circuits, qiskit.QuantumCircuit)

        json_dict = self._client.aqt_compile(
            {"qiskit_circuits": serialized_circuits, "backend": target}
        )

        return qss.compiler_output.read_json_aqt(json_dict, circuits_is_list)

    def aqt_compile_eca(
        self,
        circuit: qiskit.QuantumCircuit,
        num_equivalent_circuits: int,
        random_seed: Optional[int] = None,
        target: str = "keysight",
    ) -> "qss.compiler_output.CompilerOutput":
        """Compiles the given circuit to target AQT device with Equivalent Circuit Averaging (ECA).

        See arxiv.org/pdf/2111.04572.pdf for a description of ECA.

        Args:
            circuit: qiskit QuantumCircuit to compile.
            num_equivalent_circuits: number of logically equivalent random circuits to generate.
            random_seed: optional seed for circuit randomizer.
            target: string of target backend AQT device.
        Returns:
            object whose .circuits attribute is a list of logically equivalent QuantumCircuit(s).
            If qtrl is installed, the object's .seq attribute is a qtrl Sequence object of the
            pulse sequence corresponding to the QuantumCircuits and the .pulse_list(s) attribute is
            the list(s) of cycles.
        """
        serialized_circuit = qss.serialization.serialize_circuits(circuit)

        request_json = {
            "qiskit_circuits": serialized_circuit,
            "backend": target,
            "num_eca_circuits": num_equivalent_circuits,
        }

        if random_seed is not None:
            request_json["random_seed"] = random_seed

        json_dict = self._client.post_request("/aqt_compile", request_json)
        return qss.compiler_output.read_json_aqt(json_dict, True)

    def ibmq_compile(
        self,
        circuits: Union[qiskit.QuantumCircuit, List[qiskit.QuantumCircuit]],
        target: str = "ibmq_qasm_simulator",
    ) -> "qss.compiler_output.CompilerOutput":
        """Returns pulse schedule(s) for the given circuit(s) and target."""
        serialized_circuits = qss.serialization.serialize_circuits(circuits)

        json_dict = self._client.ibmq_compile(
            {"qiskit_circuits": serialized_circuits, "backend": target}
        )
        compiled_circuits = qss.serialization.deserialize_circuits(json_dict["qiskit_circuits"])
        pulses = applications_superstaq.converters.deserialize(json_dict["pulses"])

        if isinstance(circuits, qiskit.QuantumCircuit):
            return qss.compiler_output.CompilerOutput(
                circuits=compiled_circuits[0], pulse_sequences=pulses[0]
            )
        return qss.compiler_output.CompilerOutput(
            circuits=compiled_circuits, pulse_sequences=pulses
        )

    def qscout_compile(
        self,
        circuits: Union[qiskit.QuantumCircuit, List[qiskit.QuantumCircuit]],
        target: str = "qscout",
    ) -> "qss.compiler_output.CompilerOutput":
        """Compiles the given circuit(s) to AQT device, optimized to its native gate set.

        Args:
            circuits: qiskit QuantumCircuit(s)
        Returns:
            object whose .circuit(s) attribute is an optimized qiskit QuantumCircuit(s)
            If qtrl is installed, the object's .seq attribute is a qtrl Sequence object of the
            pulse sequence corresponding to the optimized qiskit.QuantumCircuit(s) and the
            .pulse_list(s) attribute is the list(s) of cycles.
        """
        serialized_circuits = qss.serialization.serialize_circuits(circuits)
        circuits_is_list = not isinstance(circuits, qiskit.QuantumCircuit)
        json_dict = self._client.qscout_compile(
            {"qiskit_circuits": serialized_circuits, "backend": target}
        )
        return qss.compiler_output.read_json_qscout(json_dict, circuits_is_list)

    def cq_compile(
        self,
        circuits: Union[qiskit.QuantumCircuit, List[qiskit.QuantumCircuit]],
        target: str = "cq",
    ) -> "qss.compiler_output.CompilerOutput":
        """Compiles the given circuit(s) to CQ device, optimized to its native gate set.

        Args:
            circuits: qiskit QuantumCircuit(s)
            target: the hardware to compile for
        Returns:
            object whose .circuit(s) attribute is an optimized qiskit QuantumCircuit(s)
        """
        serialized_circuits = qss.serialization.serialize_circuits(circuits)
        circuits_is_list = not isinstance(circuits, qiskit.QuantumCircuit)
        json_dict = self._client.cq_compile(
            {"qiskit_circuits": serialized_circuits, "backend": target}
        )

        return qss.compiler_output.read_json_only_circuits(json_dict, circuits_is_list)

    def neutral_atom_compile(
        self,
        circuits: Union[qiskit.QuantumCircuit, List[qiskit.QuantumCircuit]],
        target: str = "neutral_atom_qpu",
    ) -> Union[qiskit.QuantumCircuit, List[qiskit.QuantumCircuit]]:
        """Returns pulse schedule for the given circuit and target.

        Pulser must be installed for returned object to correctly deserialize to a pulse schedule.
        """
        serialized_circuits = qss.serialization.serialize_circuits(circuits)

        json_dict = self._client.neutral_atom_compile(
            {"qiskit_circuits": serialized_circuits, "backend": target}
        )
        try:
            pulses = applications_superstaq.converters.deserialize(json_dict["pulses"])
        except ModuleNotFoundError as e:
            raise applications_superstaq.SuperstaQModuleNotFoundException(
                name=str(e.name), context="neutral_atom_compile"
            )

        if isinstance(circuits, qiskit.QuantumCircuit):
            return pulses[0]
        return pulses
