from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

from ...services.get_usr_profile import get_user
from ...models.customuser import CustomUser
from ...utlis.responses import error_response, success_response


class HardDeleteUser(APIView):

    permission_classes = [IsAuthenticated, ]

    def delete(self, request, pk):

        try:
            user = get_user(pk)
            user.delete()

            return success_response(
                f"User permanently deleted successfully.",
                status=status.HTTP_200_OK,
            )

        except CustomUser.DoesNotExist:

            return error_response(
                f"User with ID = {pk} not found",
                status=status.HTTP_404_NOT_FOUND,
            )



        

