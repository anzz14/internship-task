class UnsetType:
	"""Sentinel type for fields intentionally omitted from request payloads."""

	__slots__ = ()

	def __repr__(self) -> str:
		"""Return the sentinel display name used in debugging output."""
		return "UNSET"


UNSET = UnsetType()
