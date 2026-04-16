from aidial_client import AsyncDial


class UserProfileStore:
    """
    Stores a plain-text user profile document in DIAL bucket.

    One file per user at: files/{appdata}/__user-profile/data.txt
    In-memory cache keyed by file path for fast repeated access within a session.
    """

    def __init__(self, endpoint: str):
        self.endpoint = endpoint
        self._cache: dict[str, str] = {}  # file_path -> profile text

    async def _get_profile_file_path(self, dial_client: AsyncDial) -> str:
        appdata_home = await dial_client.my_appdata_home()
        return f"files/{appdata_home.as_posix()}/__user-profile/data.txt"

    async def load_profile(self, api_key: str) -> str:
        """Load the user profile. Returns empty string if no profile exists yet."""
        dial_client = AsyncDial(base_url=self.endpoint, api_key=api_key, api_version='2025-01-01-preview')
        file_path = await self._get_profile_file_path(dial_client)

        if file_path in self._cache:
            return self._cache[file_path]

        try:
            response = await dial_client.files.download(file_path)
            text = response.get_content().decode('utf-8')
        except Exception:
            text = ""

        self._cache[file_path] = text
        return text

    async def save_profile(self, api_key: str, profile_text: str) -> None:
        """Save the user profile to DIAL bucket and update the cache."""
        dial_client = AsyncDial(base_url=self.endpoint, api_key=api_key, api_version='2025-01-01-preview')
        file_path = await self._get_profile_file_path(dial_client)
        await dial_client.files.upload(url=file_path, file=profile_text.encode('utf-8'))
        self._cache[file_path] = profile_text
