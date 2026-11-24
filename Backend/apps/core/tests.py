from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory

from apps.core.models.customuser import CustomUser
from apps.core.models.device import Devices, DeviceType
from apps.core.models.tank import Tank, TankStatus
from apps.core.permissions import IsSuperAdmin, LicensePermission
from apps.core.serializers.tank import TankDeviceConfigSerializer


def make_user(email, role, **extra):
    return CustomUser.objects.create_user(email=email, password="pw12345!x", role=role, **extra)


def request_for(user):
    request = APIRequestFactory().get("/")
    request.user = user
    return request


class PermissionTests(TestCase):

    def test_is_superadmin_rejects_anonymous(self):
        from django.contrib.auth.models import AnonymousUser
        self.assertFalse(IsSuperAdmin().has_permission(request_for(AnonymousUser()), None))

    def test_is_superadmin_by_role(self):
        sa = make_user("sa@x.com", CustomUser.Role.SUPERADMIN)
        admin = make_user("ua@x.com", CustomUser.Role.USER_ADMIN, created_by=sa)
        self.assertTrue(IsSuperAdmin().has_permission(request_for(sa), None))
        self.assertFalse(IsSuperAdmin().has_permission(request_for(admin), None))

    def test_license_rejects_anonymous(self):
        from django.contrib.auth.models import AnonymousUser
        self.assertFalse(LicensePermission().has_permission(request_for(AnonymousUser()), None))

    def test_license_superadmin_always_allowed(self):
        sa = make_user("sa@x.com", CustomUser.Role.SUPERADMIN)
        self.assertTrue(LicensePermission().has_permission(request_for(sa), None))

    def test_license_expired_and_deactivated_block_user_admin_and_children(self):
        sa = make_user("sa@x.com", CustomUser.Role.SUPERADMIN)
        admin = make_user("ua@x.com", CustomUser.Role.USER_ADMIN, created_by=sa)
        child = make_user("c@x.com", CustomUser.Role.PARENT_USER, created_by=admin, user_admin=admin)
        profile = admin.user_profile
        perm = LicensePermission()

        # profiles start inactive until licensed
        self.assertFalse(perm.has_permission(request_for(admin), None))
        profile.is_profile_active = True
        profile.save()
        admin.refresh_from_db()
        self.assertTrue(perm.has_permission(request_for(admin), None))

        profile.validity_to_date = timezone.now().date() - timedelta(days=1)
        profile.save()
        for u in (admin, child):
            u.refresh_from_db()
            self.assertFalse(perm.has_permission(request_for(u), None))

        profile.validity_to_date = None
        profile.is_profile_active = False
        profile.save()
        child.refresh_from_db()
        self.assertFalse(perm.has_permission(request_for(child), None))


class TankDeviceConfigSerializerTests(TestCase):

    def setUp(self):
        sa = make_user("sa@x.com", CustomUser.Role.SUPERADMIN)
        self.admin = make_user("ua@x.com", CustomUser.Role.USER_ADMIN, created_by=sa)
        self.profile = self.admin.user_profile
        mk = lambda sn, t: Devices.objects.create(serial_number=sn, device_type=t, user_profile=self.profile)
        self.tx = mk("TX1", DeviceType.TRANSMITTER)
        self.gw = mk("GW1", DeviceType.GATEWAY)
        self.rx = mk("RX1", DeviceType.RECEIVER)
        self.pc = mk("PC1", DeviceType.PUMP_CONTROLLER)
        self.tank = Tank.objects.create(
            name="T", user_profile=self.profile, capacity_litres=1000, created_by=self.admin,
        )

    def payload(self, **over):
        data = {
            "requirements": {"transmitter": 1, "gateway": 1, "receiver": 1, "pump_controller": 1},
            "devices": {
                "transmitter": [self.tx.id], "gateway": [self.gw.id],
                "receiver": [self.rx.id], "pump_controller": [self.pc.id],
            },
            "uplink": [self.tx.id, self.gw.id],
            "downlink": [self.rx.id, self.pc.id],
        }
        data.update(over)
        return data

    def run_serializer(self, data):
        s = TankDeviceConfigSerializer(data=data, context={"tank": self.tank})
        return s, s.is_valid()

    def test_valid_config(self):
        _, ok = self.run_serializer(self.payload())
        self.assertTrue(ok)

    def test_unknown_chain_device_is_validation_error_not_crash(self):
        s, ok = self.run_serializer(self.payload(uplink=[self.tx.id, 99999]))
        self.assertFalse(ok)
        s, ok = self.run_serializer(self.payload(downlink=[99998, self.pc.id]))
        self.assertFalse(ok)


class TankToggleStatusTests(TestCase):

    def setUp(self):
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import RefreshToken
        sa = make_user("sa@x.com", CustomUser.Role.SUPERADMIN)
        self.admin = make_user("ua@x.com", CustomUser.Role.USER_ADMIN, created_by=sa)
        self.admin.session_id = "s1"
        self.admin.save(update_fields=["session_id"])
        token = RefreshToken.for_user(self.admin)
        token["session_id"] = "s1"
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
        profile = self.admin.user_profile
        profile.is_profile_active = True
        profile.validity_to_date = timezone.localdate() + timedelta(days=30)
        profile.save()
        self.tank = Tank.objects.create(
            name="T", user_profile=self.admin.user_profile, capacity_litres=1000,
            low_level_thresholds=20, high_level_thresholds=90, created_by=self.admin,
        )

    def activate_at(self, level):
        Tank.objects.filter(pk=self.tank.pk).update(current_level_precent=level, is_active=False)
        res = self.client.post(f"/AQUACOMMUNICA/web/core/tank-active-toggle/{self.tank.pk}/")
        self.assertEqual(res.status_code, 200, res.content)
        self.tank.refresh_from_db()
        return self.tank.status

    def test_status_uses_tank_thresholds(self):
        self.assertEqual(self.activate_at(95), TankStatus.OVERFLOW)
        self.assertEqual(self.activate_at(50), TankStatus.NORMAL)
        self.assertEqual(self.activate_at(15), TankStatus.LOW)
        self.assertEqual(self.activate_at(5), TankStatus.CRITICAL)


class LicenseValidityMiddlewareTests(TestCase):
    URL = "/AQUACOMMUNICA/web/core/user-profile/"

    def setUp(self):
        from rest_framework.test import APIClient
        self.APIClient = APIClient
        self.sa = make_user("sa@x.com", CustomUser.Role.SUPERADMIN)
        self.dealer = make_user("d@x.com", CustomUser.Role.DEALER, created_by=self.sa)
        self.admin = make_user("ua@x.com", CustomUser.Role.USER_ADMIN, created_by=self.sa)
        self.parent = make_user("p@x.com", CustomUser.Role.PARENT_USER, created_by=self.admin, user_admin=self.admin)
        self.child = make_user("c@x.com", CustomUser.Role.CHILD_USER, created_by=self.admin, user_admin=self.admin)

    def client_for(self, user):
        from rest_framework_simplejwt.tokens import RefreshToken
        user.session_id = "s1"
        user.save(update_fields=["session_id"])
        token = RefreshToken.for_user(user)
        token["session_id"] = "s1"
        client = self.APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
        return client

    def set_license(self, profile, active=True, days=30):
        profile.is_profile_active = active
        profile.validity_to_date = timezone.localdate() + timedelta(days=days) if days is not None else None
        profile.save()

    def status(self, user, url=None):
        return self.client_for(user).get(url or self.URL).status_code

    def test_valid_license_passes_for_all_roles(self):
        self.set_license(self.admin.user_profile)
        self.set_license(self.dealer.dealer_profile)
        for u in (self.admin, self.parent, self.child, self.dealer):
            self.assertEqual(self.status(u), 200, u.role)

    def test_blocked_when_inactive_expired_or_missing_validity(self):
        for kwargs in ({"active": False}, {"days": -1}, {"days": None}):
            self.set_license(self.admin.user_profile, **kwargs)
            self.set_license(self.dealer.dealer_profile, **kwargs)
            for u in (self.admin, self.parent, self.child, self.dealer):
                self.assertEqual(self.status(u), 403, (u.role, kwargs))

    def test_children_follow_their_admins_license(self):
        self.set_license(self.admin.user_profile, days=-1)
        res = self.client_for(self.child).get(self.URL)
        self.assertEqual(res.status_code, 403)
        self.assertFalse(res.json()["success"])

    def test_superadmin_not_checked_and_logout_stays_open(self):
        self.assertEqual(self.status(self.sa), 200)
        self.set_license(self.admin.user_profile, days=-1)
        res = self.client_for(self.admin).post(
            "/AQUACOMMUNICA/web/core/logout/", {"refresh": "x"}, format="json"
        )
        self.assertNotIn("license", str(res.json().get("message", "")).lower())

    def test_no_or_bad_token_left_to_drf(self):
        self.assertEqual(self.APIClient().get(self.URL).status_code, 401)
        client = self.APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer garbage")
        self.assertEqual(client.get(self.URL).status_code, 401)

    def test_users_of_deactivated_dealer_blocked(self):
        self.set_license(self.admin.user_profile)
        self.admin.dealer = self.dealer
        self.admin.save()
        self.assertEqual(self.status(self.child), 200)
        self.dealer.is_active = False
        self.dealer.save()
        for u in (self.admin, self.parent, self.child):
            self.assertEqual(self.status(u), 403, u.role)
