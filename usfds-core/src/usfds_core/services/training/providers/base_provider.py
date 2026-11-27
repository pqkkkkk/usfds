"""Abstract remote compute provider interface and registry (ISS-009)."""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple

from usfds_core.domain.schemas.training_payload import (
	RemoteJobStatus,
	RemoteTrainingJobSpec,
)


class IRemoteComputeProvider(ABC):
	"""Port for offloading a TrainingRun to an external compute provider."""

	@property
	@abstractmethod
	def provider_id(self) -> str:
		"""Stable identifier used as compute_target (e.g. 'modal')."""
		pass

	@property
	@abstractmethod
	def display_name(self) -> str:
		"""Human-readable name displayed in UI."""
		pass

	@property
	def supported_tiers(self) -> List[str]:
		"""Resource tiers supported by this provider (e.g. ['cpu', 'gpu'])."""
		return ["cpu", "gpu"]

	@abstractmethod
	def is_available(self) -> Tuple[bool, Optional[str]]:
		"""Return (True, None) if configured and usable, else (False, reason)."""
		pass

	@abstractmethod
	def submit(self, job_spec: RemoteTrainingJobSpec) -> str:
		"""Submit a remote training job and return its external_job_id."""
		pass

	@abstractmethod
	def poll(self, external_job_id: str, timeout_seconds: float = 5.0) -> RemoteJobStatus:
		"""Check the current status of a remote job without blocking for long."""
		pass

	def cancel(self, external_job_id: str) -> bool:
		"""Best-effort cancel hook reserved for ISS-011."""
		return False


class RemoteProviderRegistry:
	"""In-process registry mapping provider_id -> IRemoteComputeProvider."""

	def __init__(self) -> None:
		self._providers: Dict[str, IRemoteComputeProvider] = {}

	def register(self, provider: IRemoteComputeProvider) -> None:
		self._providers[provider.provider_id.strip().lower()] = provider

	def get(self, provider_id: str) -> Optional[IRemoteComputeProvider]:
		if not provider_id:
			return None
		return self._providers.get(provider_id.strip().lower())

	def list_providers(self) -> List[IRemoteComputeProvider]:
		return list(self._providers.values())

	def list_available_providers(self) -> List[IRemoteComputeProvider]:
		available: List[IRemoteComputeProvider] = []
		for provider in self._providers.values():
			ok, _ = provider.is_available()
			if ok:
				available.append(provider)
		return available

	def first_available(self) -> Optional[IRemoteComputeProvider]:
		for provider in self._providers.values():
			ok, _ = provider.is_available()
			if ok:
				return provider
		return None
