import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.common.exceptions import NotFoundError
from app.modules.library.models.log_type import LogType
from app.modules.library.models.sample_log import SampleLog
from app.modules.library.schemas import SampleLogCreate
from app.modules.library.services.sample_log_service import SampleLogService


def _make_log_type() -> LogType:
    lt = LogType()
    lt.id = uuid.uuid4()
    return lt


def _make_sample() -> SampleLog:
    s = SampleLog()
    s.id = uuid.uuid4()
    s.log_type_id = uuid.uuid4()
    s.raw_log = "1,2,3"
    s.label = "normal"
    return s


def _make_service(
    *,
    log_type_get: LogType | None = None,
    sample_get: SampleLog | None = None,
):
    sample_repo = MagicMock()
    sample_repo.get_by_id = AsyncMock(return_value=sample_get)
    sample_repo.list_by_log_type = AsyncMock(return_value=[])
    sample_repo.create = AsyncMock(side_effect=lambda s: s)
    sample_repo.delete = AsyncMock(return_value=None)

    log_type_repo = MagicMock()
    log_type_repo.get_by_id = AsyncMock(return_value=log_type_get)

    return SampleLogService(sample_repo, log_type_repo), sample_repo, log_type_repo


class TestSampleLogServiceCreate:
    """Tests for SampleLogService.create()."""

    async def test_creates(self):
        """Should attach to log_type and create."""
        # Arrange
        log_type = _make_log_type()
        service, _, _ = _make_service(log_type_get=log_type)
        request = SampleLogCreate(raw_log="1,2,3")

        # Act
        result = await service.create(log_type.id, request, current_user_id=uuid.uuid4())

        # Assert
        assert result.log_type_id == log_type.id
        assert result.raw_log == "1,2,3"

    async def test_raises_not_found_when_log_type_missing(self):
        """Should raise NotFoundError."""
        # Arrange
        service, _, _ = _make_service(log_type_get=None)
        request = SampleLogCreate(raw_log="x")

        # Act / Assert
        with pytest.raises(NotFoundError):
            await service.create(uuid.uuid4(), request, current_user_id=uuid.uuid4())


class TestSampleLogServiceDelete:
    """Tests for SampleLogService.delete()."""

    async def test_deletes(self):
        """Should fetch and delete."""
        # Arrange
        sample = _make_sample()
        service, repo, _ = _make_service(sample_get=sample)

        # Act
        await service.delete(sample.id)

        # Assert
        repo.delete.assert_awaited_once_with(sample)

    async def test_raises_not_found(self):
        """Should raise NotFoundError when missing."""
        # Arrange
        service, _, _ = _make_service(sample_get=None)

        # Act / Assert
        with pytest.raises(NotFoundError):
            await service.delete(uuid.uuid4())
