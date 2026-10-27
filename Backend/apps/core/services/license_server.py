import time
import logging
import requests
from datetime import datetime

from django.conf import settings


log_license_server = logging.getLogger('aquacommunica.licenseserver')


def check_datetime(date_str):
    try:
        if not date_str:
            return None
        if isinstance(date_str, str):
            return datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
        return date_str
    except Exception:
        return None


def _parse_license_date(raw):
    """Return the date part of a license server datetime string, or None on any failure."""
    dt = check_datetime(raw)
    return dt.date() if dt is not None else None


def buid_license_registration_payload(profile):
    """Build the customer payload expected by the license server.

    Uses the profile's contact email as a device identifier so each profile
    can be registered with a distinct identity.
    """
    payload = {
        "CustomerName":          profile.first_name,
        "PhoneNumber":           profile.phone_number,
        "CustomerEmail":         profile.contact_email,
        "GSTNumber":             profile.gst_number or '',
        "CustomerContactPerson": profile.first_name + " " + profile.last_name,
        "CustomerAddress":       profile.address,

        # this is important. 
        # ig this differentiates diff profiles else it'll return some same older ID again. 
        "DeviceIdentifier1":     profile.contact_email,
        "DeviceModel":           settings.DEVICE_MODEL,
        "DeviceType":            settings.DEVICE_TYPE,
        "ProjectName":           settings.PROJECT_NAME,
    }

    return payload



def register_with_license_server(profile):
    """Register a user profile with the external license server.

    Returns a dictionary with ``success`` and either the customer ID or an
    error message.
    """
    
    # Build the registration payload using the user profile details.
    payload = buid_license_registration_payload(profile)

    try:
        # Log the registration endpoint before sending the API request.
        log_license_server.info(
            f"Sending registration request to: "
            f"{settings.PRODUCT_REGISTRATION_URL}"
        )

        # Log the payload for debugging and troubleshooting purposes.
        log_license_server.info(f"Registration payload: {payload}")

        # Send the registration data to the external license server.
        # The payload is automatically serialized to JSON.
        # The request will raise a Timeout exception if it takes longer
        # than 30 seconds.
        response = requests.post(
            settings.PRODUCT_REGISTRATION_URL,
            json=payload,
            timeout=30
        )

        # Log the HTTP status code and response body for diagnostics.
        log_license_server.info(
            f"Registration response status: {response.status_code}"
        )
        log_license_server.info(
            f"Registration response: {response.text}"
        )

        # Raise an HTTPError for unsuccessful HTTP status codes (4xx or 5xx).
        response.raise_for_status()

        # Parse the JSON response returned by the license server.
        data = response.json()

        # Verify that the server confirms success and provides a customer ID.
        if data.get('status') == 'Success' and data.get('CustomerId'):

            # Log the successful registration and the assigned customer ID.
            log_license_server.info(
                f"Registration successful. "
                f"Customer ID: {data.get('CustomerId')}"
            )

            # Return the customer ID so the caller can update the profile.
            return {
                'success': True,
                'customer_id': data['CustomerId']
            }

        else:
            # Handle valid JSON responses that do not meet the success criteria.
            log_license_server.info(
                f"Registration failed. Response data: {data}"
            )

            # Return the error message provided by the server, if available.
            return {
                'success': False,
                'error': (
                    f"Registration failed: "
                    f"{data.get('message', 'Invalid response from license server')}"
                )
            }

    except requests.exceptions.Timeout as e:
        # Handle requests that exceed the configured timeout.
        log_license_server.info(
            f"License server timeout: {str(e)}"
        )

        return {
            'success': False,
            'error': 'License server timeout. Please try again later.'
        }

    except requests.exceptions.ConnectionError as e:
        # Handle network failures, DNS issues, or connection failures.
        log_license_server.info(
            f"License server connection error: {str(e)}"
        )

        return {
            'success': False,
            'error': (
                'Cannot connect to license server. '
                'Please check your network connection.'
            )
        }

    except requests.exceptions.HTTPError as e:
        # Handle HTTP errors such as 400, 401, 403, or 500.
        log_license_server.info(
            f"License server HTTP error: {str(e)}"
        )

        return {
            'success': False,
            'error': f'License server error: {e.response.status_code}'
        }

    except Exception as e:
        # Handle unexpected errors, such as invalid JSON responses
        # or other exceptions not covered by the handlers above.
        log_license_server.info(
            f"Unexpected error during registration: {str(e)}"
        )

        return {
            'success': False,
            'error': f'Unexpected error: {str(e)}'
        }


def poll_license_authentication(customer_id, timeout_sec=120, interval_sec=20):
    # customer_id => given by ls from registration time

    payload = {"CustomerId": customer_id}
    start_time = time.time()
    poll_count = 0


    while time.time() - start_time < timeout_sec:

        poll_count += 1

        try: 
            response = requests.post(
                    settings.PRODUCT_AUTH_URL,
                    json=payload,
                    timeout=30
                )

            response.raise_for_status()
                
            data = response.json()
            auth_status = data.get('Authenticationstatus', '')

            # Success case
            if auth_status == 'Approve':
                
                return {
                    'success': True,
                    'status': 'Approve',
                    'data': data
                }

            # Expired license
            if 'expired' in auth_status.lower():

                return {
                    'success': True,
                    'status': 'Expired',
                    'data': data
                }

            # Still waiting - continue polling
            if 'waiting' in auth_status.lower() or auth_status == 'Pending':
                
                time.sleep(interval_sec)
                continue

             # Unknown status - treat as error
            return {
                'success': False,
                'error': f'Unexpected authentication status: {auth_status}'
            }

        
        except requests.exceptions.Timeout as e:
            return {
                'success': False,
                'error': 'License server not responding. Please try again later.'
            }
        except requests.exceptions.ConnectionError as e:
            return {
                'success': False,
                'error': 'Cannot connect to license server. Check your network connection.'
            }
        except requests.exceptions.HTTPError as e:
            return {
                'success': False,
                'error': f'License server error: {e.response.status_code}. Try again later.'
            }
        except Exception as e:
            return {
                'success': False,
                'error': 'Unexpected error during validation. Please try again.'
            }

    # Timeout
    elapsed = time.time() - start_time
    return {
        'success': False,
        'error': f'Validation timeout - License not approved yet. Please try again later. ({poll_count} attempts over {int(elapsed)}s)'
    }


def fetch_user_profile_from_license_server(customer_id):

    payload = {"CustomerId": customer_id}

    try:
        response = requests.post(
            settings.PRODUCT_AUTH_URL,
            json=payload,
            timeout=30
        )

        response.raise_for_status()
        data = response.json()
        auth_status = data.get('Authenticationstatus', '')

        if not auth_status:

            return {
                "success": False,
                "error": 'No response from license server.'
            }

        return {
            "success": True,
            'status': auth_status,
            'data': data,
        }

    except requests.exceptions.Timeout:

        return {
            'success': False, 
            'error': 'License server timed out. Try again.'
        }
    except requests.exceptions.ConnectionError:

        return {
            'success': False, 
            'error': 'Cannot connect to license server.'
        }
    except requests.exceptions.HTTPError as e:

        return {
            'success': False, 
            'error': f'License server error: {e.response.status_code}'
        }
    except Exception as e:
       
        return {
            'success': False, 
            'error': f'Unexpected error: {str(e)}'
        }


def _build_user_profile_sync_diff(profile, auth_data):

    def _si(val):
        try:
            return int(val or 0)
        except (ValueError, TypeError):
            return 0

    incoming_total_license_unit = _si(auth_data.get('NumberOfLicence'))
    incoming_total_device_count = _si(auth_data.get('PalmtecCount'))
    incoming_total_user_count = _si(auth_data.get('TotalUserCount'))
    incoming_parent_user_count = _si(auth_data.get('PremiumUserCount'))
    incoming_child_user_count = _si(auth_data.get('IntermediateUserCount'))


    error = None
    if incoming_total_license_unit > 0 and (incoming_total_device_count + incoming_total_user_count) > incoming_total_license_unit:

        error = (
            f"License config error: device slots ({incoming_total_device_count}) + "
            f"user slots ({incoming_total_user_count}) = {incoming_total_device_count + incoming_total_user_count} "
            f"exceeds total licensed units ({incoming_total_license_unit}). "
            "Contact the license server administrator."
        )


    from_date_raw = auth_data.get('ProductFromDate')
    to_date_raw = auth_data.get('ProductToDate')

    incoming_date_from = _parse_license_date(from_date_raw)
    incoming_date_to   = _parse_license_date(to_date_raw)

    return {
        'current': {
            'total_license_unit': profile.total_licence_unit or 0,
            'total_device_count': profile.total_device_count or 0,
            'total_user_count': profile.total_user_count or 0,
            'parent_user_count': profile.parent_user_count or 0,
            'child_user_count': profile.child_user_count or 0,
            'validity_from_date': str(profile.validity_from_date) if profile.validity_from_date else None,
            'validity_to_date': str(profile.validity_to_date) if profile.validity_to_date else None,
        },
        'incoming': {
            'total_license_unit': incoming_total_license_unit,
            'total_device_count': incoming_total_device_count,
            'total_user_count': incoming_total_user_count,
            'parent_user_count': incoming_parent_user_count,
            'child_user_count': incoming_child_user_count,
            'validity_from_date': incoming_date_from,
            'validity_to_date': incoming_date_to,
            'authentication_status': auth_data.get('Authenticationstatus'),
            'product_registration_id': _si(auth_data.get('ProductRegistrationId')),
            'unique_identifier': auth_data.get('UniqueIDentifier', ''),
        },
        'error': error,
    }
