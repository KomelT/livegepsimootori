import hashlib
import hmac
from datetime import timedelta

from django.conf import settings
from django.test.client import MULTIPART_CONTENT
from django.utils.timezone import now
from rest_framework import status
from rest_framework.test import APIClient

from routechoices.api.tests import EssentialApiBase
from routechoices.core.models import Club


class LemonSqueezyAPIClient(APIClient):
    @staticmethod
    def get_signature(data):
        digest = hmac.new(
            settings.LEMONSQUEEZY_SIGNATURE.encode("utf-8"),
            msg=data,
            digestmod=hashlib.sha256,
        ).hexdigest()
        return digest

    def post(
        self,
        path,
        data=None,
        content_type=MULTIPART_CONTENT,
        **kwargs,
    ):
        data = self._encode_json({} if data is None else data, content_type)
        post_data = self._encode_data(data, content_type)
        return super().post(
            path,
            data,
            content_type,
            HTTP_X_SIGNATURE=self.get_signature(post_data[0]),
            **kwargs,
        )


class WebHookTestCase(EssentialApiBase):
    def setUp(self):
        super().setUp()
        self.club = Club.objects.create(name="Kemiön Kiilat", slug="kiilat")
        self.club.creation_date = now() - timedelta(days=14)
        self.club.admins.set([self.user])
        self.ls_client = LemonSqueezyAPIClient(HTTP_HOST="api.track.meshtrail.si")

    def test_invalid_signature(self):
        url = self.reverse_and_check(
            "webhooks:lemonsqueezy_webhook", "/webhooks/lemonsqueezy"
        )
        client = APIClient(HTTP_HOST="api.track.meshtrail.si")
        res = client.post(url, {"random": 123})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_valid_signature(self):
        url = self.reverse_and_check(
            "webhooks:lemonsqueezy_webhook", "/webhooks/lemonsqueezy"
        )
        res = self.ls_client.post(url, {"random": 123}, content_type="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_upgrade_club(self):
        url = self.reverse_and_check(
            "webhooks:lemonsqueezy_webhook", "/webhooks/lemonsqueezy"
        )
        res = self.ls_client.post(
            url,
            {
                "data": {
                    "id": "123456",
                    "attributes": {
                        "first_order_item": {"variant_id": 1102505, "order_id": 123456}
                    },
                },
                "meta": {"custom_data": {"club": "kiilat"}},
            },
            HTTP_X_EVENT_NAME="order_created",
            content_type="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.club.refresh_from_db()
        self.assertTrue(self.club.upgraded)
        self.assertEqual(self.club.order_id, "123456")
        self.assertTrue(self.club.can_modify_events)

    def test_downgrade_club(self):
        url = self.reverse_and_check(
            "webhooks:lemonsqueezy_webhook", "/webhooks/lemonsqueezy"
        )
        self.club.upgraded = True
        self.club.order_id = "123456"
        self.club.save()
        res = self.ls_client.post(
            url,
            {"data": {"attributes": {"order_id": 123456, "variant_id": 1102505}}},
            HTTP_X_EVENT_NAME="subscription_expired",
            content_type="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.club.refresh_from_db()
        self.assertFalse(self.club.upgraded)
        self.assertEqual(self.club.order_id, "")
        self.assertFalse(self.club.can_modify_events)

    def test_pause_club_subscription(self):
        url = self.reverse_and_check(
            "webhooks:lemonsqueezy_webhook", "/webhooks/lemonsqueezy"
        )
        self.club.upgraded = True
        self.club.order_id = "123456"
        self.club.save()
        self.assertFalse(self.club.subscription_paused)
        self.assertTrue(self.club.can_modify_events)
        res = self.ls_client.post(
            url,
            {
                "data": {
                    "attributes": {
                        "order_id": 123456,
                        "variant_id": 1102505,
                        "pause": {"mode": "void"},
                    }
                }
            },
            HTTP_X_EVENT_NAME="subscription_paused",
            content_type="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.club.refresh_from_db()
        self.assertTrue(self.club.subscription_paused)
        self.assertFalse(self.club.can_modify_events)

    def test_unpause_club_subscription(self):
        url = self.reverse_and_check(
            "webhooks:lemonsqueezy_webhook", "/webhooks/lemonsqueezy"
        )
        self.club.upgraded = True
        self.club.order_id = "123456"
        self.club.subscription_paused_at = now() - timedelta(days=2)
        self.club.save()
        self.assertTrue(self.club.subscription_paused)
        self.assertFalse(self.club.can_modify_events)
        res = self.ls_client.post(
            url,
            {
                "data": {
                    "attributes": {
                        "order_id": 123456,
                        "variant_id": 1102505,
                    }
                }
            },
            HTTP_X_EVENT_NAME="subscription_unpaused",
            content_type="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.club.refresh_from_db()
        self.assertFalse(self.club.subscription_paused)
        self.assertTrue(self.club.can_modify_events)
