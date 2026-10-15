import logging
import requests

from django.conf import settings


log_license_server = logging.getLogger('aquacommunica.licenseserver')



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