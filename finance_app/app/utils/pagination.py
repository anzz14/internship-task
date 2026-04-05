def get_pagination(page: int, page_size: int) -> tuple[int, int]:
	"""Normalize pagination inputs and return safe page size with offset."""
	safe_page = max(page, 1)
	safe_page_size = min(max(page_size, 1), 100)
	offset = (safe_page - 1) * safe_page_size
	return safe_page_size, offset


def get_total_pages(total: int, page_size: int) -> int:
	"""Compute total page count for a total row count and page size."""
	if total == 0:
		return 0
	return (total + page_size - 1) // page_size

