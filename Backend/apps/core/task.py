import logging

from celery import shared_task

from .models.profiles import DealerProfile, UserProfile
from .services.license_server import poll_license_authentication, _parse_license_date

action_log = logging.getLogger('aquacommunica.action.log')


@shared_task(bind=True, max_retries=3)
def poll_user_profile_license(self, pro_id: int) -> None:
    # pro_id is profile_id(pk)
    try:
        profile = UserProfile.objects.get(id=pro_id)

    except UserProfile.DoesNotExist:
        action_log.warning(f"License poll skipped, profile not found: id={pro_id}")
        return

    is_dealer_user_profile = profile.client_type == UserProfile.ClientType.DEALER

    try:
        auth_result = poll_license_authentication(profile.profile_id)

        if not auth_result['success']:
            action_log.warning(
                f"License poll failed, status set to pending: id={pro_id}, "
                f"profile_id={profile.profile_id}"
            )

            profile.authentication_status = UserProfile.AuthStatus.PENDING
            profile.save(update_fields=['authentication_status'])
            return

        auth_data = auth_result.get('data', {})
        auth_status = auth_result.get('status')


        if auth_status == 'Approve':
            profile.authentication_status = UserProfile.AuthStatus.APPROVED
            profile.is_profile_active = True
        elif auth_status == 'Expired':
            profile.authentication_status = UserProfile.AuthStatus.EXPIRED
        elif auth_status == 'Block':
            profile.authentication_status = UserProfile.AuthStatus.BLOCKED


        if auth_status == 'Approve':
            def _safe_int(val, default=0):
                try:
                    return int(val or default)
                except (ValueError, TypeError):
                    return default

            # using bus ticket license profile for checking should have to change
            total_license_unit = _safe_int(auth_data.get('NumberOfLicence'))
            total_device_count = _safe_int(auth_data.get('PalmtecCount'))
            total_user_count = _safe_int(auth_data.get('TotalUserCount'))
            parent_user_count = _safe_int(auth_data.get('PremiumUserCount'))
            child_user_count = _safe_int(auth_data.get('IntermediateUserCount'))

            if not is_dealer_user_profile and total_license_unit > 0 and (total_device_count + total_user_count) > total_license_unit:

                profile.authentication_status = UserProfile.AuthStatus.PENDING
                profile.error_message = (
                    f"License config error : device slot ({total_device_count}) + "
                    f'user slots ({total_user_count}) = {total_device_count + total_user_count} '
                    f'exceeds total licensed units ({total_license_unit}). '
                    'Contact the license server administrator.'
                )

                profile.save()
                action_log.warning(
                    f"License poll config error: id={pro_id}, "
                    f"devices={total_device_count}, users={total_user_count}, "
                    f"licensed_units={total_license_unit}"
                )
                return

            profile.product_registration_id = auth_data.get('ProductRegistrationId')
            profile.unique_identifier = auth_data.get('UniqueIDentifier')
            profile.validity_from_date = _parse_license_date(auth_data.get('ProductFromDate'))
            profile.validity_to_date = _parse_license_date(auth_data.get('ProductToDate'))


            if not is_dealer_user_profile:
                profile.total_licence_unit = total_license_unit
                profile.total_device_count = total_device_count
                profile.total_user_count = total_user_count
                profile.parent_user_count = parent_user_count
                profile.child_user_count = child_user_count

        profile.save()

        action_log.info(
            f"License poll completed: id={pro_id}, license_status={auth_status}, "
            f"authentication_status={profile.authentication_status}"
        )

    except Exception as exc:
        action_log.error(
            f"License poll error, retrying: id={pro_id}, error={exc}, "
            f"attempt={self.request.retries + 1}/{self.max_retries}"
        )
        raise self.retry(exc=exc, countdown=120)

    finally:
        # Safety net: if the task ends for any reason while status is still
        # VALIDATING, reset to PENDING so admins can retry. This also covers
        # the case where a Celery worker is killed mid-task (on next heartbeat
        # Celery marks the task as failed and this finally runs on the retry).
        try:
            profile = UserProfile.objects.get(id=pro_id)
            if profile.authentication_status == UserProfile.AuthStatus.VALIDATING:
                profile.authentication_status = UserProfile.AuthStatus.PENDING
                profile.save(update_fields=['authentication_status'])
                action_log.warning(f"License poll reset VALIDATING to PENDING: id={pro_id}")
        except Exception as e:
            action_log.error(f"License poll could not reset VALIDATING: id={pro_id}, error={e}")
    