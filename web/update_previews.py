"""Only close headed previews owned by this Local application."""
import asyncio


class UpdatePreviews:
    def _owners(self):
        from web import activity_runner, bundle_runner
        return (activity_runner, bundle_runner)

    def count(self):
        return sum(owner.kept_count() for owner in self._owners())

    async def close(self):
        for owner in self._owners():
            await asyncio.wait_for(owner.close_all_kept(), timeout=20)
