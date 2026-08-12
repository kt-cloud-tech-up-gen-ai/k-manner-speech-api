from tests.test_new_apis import ApiTestCase


class ExtendedProfileTests(ApiTestCase):
    def test_extended_profile_round_trip(self):
        self._authenticate()
        payload = {
            "name": "김학습",
            "age": 24,
            "learning_goal_other": "한국 대학원 면접 준비",
            "native_language": "ko",
            "gender": "other",
            "learning_goals": ["business", "other"],
            "study_frequency": "three_per_week",
            "push_enabled": True,
        }

        written = self.client.put("/auth/me/profile", json=payload)

        self.assertEqual(written.status_code, 200, msg="AC-T3-PROFILE-ROUNDTRIP")
        fetched = self.client.get("/auth/me").json()["profile"]
        for key, expected in payload.items():
            actual = sorted(fetched[key]) if isinstance(expected, list) else fetched[key]
            expected = sorted(expected) if isinstance(expected, list) else expected
            self.assertEqual(actual, expected, msg="AC-T3-PROFILE-ROUNDTRIP")

    def test_invalid_age_does_not_change_profile(self):
        self._authenticate()
        payload = {
            "name": "김학습",
            "age": 24,
            "learning_goal_other": None,
            "native_language": "ko",
            "gender": None,
            "learning_goals": [],
            "study_frequency": None,
            "push_enabled": False,
        }
        self.client.put("/auth/me/profile", json=payload)
        response = self.client.put("/auth/me/profile", json={**payload, "age": -1})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.client.get("/auth/me").json()["profile"]["age"], 24)
