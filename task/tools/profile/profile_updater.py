from aidial_client import AsyncDial

from task.prompts_profile import (
    PROFILE_CHECK_SYSTEM,
    PROFILE_CHECK_USER,
    PROFILE_UPDATE_SYSTEM,
    PROFILE_UPDATE_USER,
)
from task.tools.profile.user_profile_store import UserProfileStore


class ProfileUpdater:
    """
    Checks whether a conversation exchange reveals new user information and,
    if so, updates the stored user profile using a mini model.

    Designed to be called as a fire-and-forget asyncio task after the final
    agent response is streamed to the user (~1% of calls trigger an actual update).
    """

    def __init__(
        self,
        endpoint: str,
        mini_deployment_name: str,
        profile_store: UserProfileStore,
    ):
        self.endpoint = endpoint
        self.mini_deployment_name = mini_deployment_name
        self.profile_store = profile_store

    async def maybe_update_profile(
        self,
        api_key: str,
        user_message: str,
        assistant_message: str,
    ) -> None:
        try:
            profile = await self.profile_store.load_profile(api_key)

            client = AsyncDial(
                base_url=self.endpoint,
                api_key=api_key,
                api_version='2025-01-01-preview',
            )

            # Step 1: fast check — does this exchange reveal new user info?
            check_response = await client.chat.completions.create(
                deployment_name=self.mini_deployment_name,
                messages=[
                    {"role": "system", "content": PROFILE_CHECK_SYSTEM},
                    {"role": "user", "content": PROFILE_CHECK_USER.format(
                        profile=profile or "(no profile yet)",
                        user_message=user_message,
                        assistant_message=assistant_message,
                    )},
                ],
                stream=False,
                max_tokens=5,
                temperature=0.0,
            )
            verdict = check_response.choices[0].message.content.strip().lower()
            print(f"[ProfileUpdater] check verdict: {verdict!r}")

            if verdict != "true":
                return  # fast path — no new info

            # Step 2: update the profile
            update_response = await client.chat.completions.create(
                deployment_name=self.mini_deployment_name,
                messages=[
                    {"role": "system", "content": PROFILE_UPDATE_SYSTEM},
                    {"role": "user", "content": PROFILE_UPDATE_USER.format(
                        profile=profile or "(no profile yet)",
                        user_message=user_message,
                        assistant_message=assistant_message,
                    )},
                ],
                stream=False,
                temperature=0.2,
            )
            new_profile = update_response.choices[0].message.content.strip()

            await self.profile_store.save_profile(api_key, new_profile)
            print(f"[ProfileUpdater] Profile updated.")

        except Exception as e:
            print(f"[ProfileUpdater] Error during profile update: {e}")
