from rest_framework import status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from ...models.customuser import CustomUser
from ...serializers.tank import createTankSerislizer
from ...utlis.responses import error_response, success_response


class AddTankView(APIView):

    permission_classes = [
        IsAuthenticated,
    ]

    PARENT_USER = CustomUser.Role.PARENT_USER
    USER_ADMIN  = CustomUser.Role.USER_ADMIN

    def post(self, request):

        user = request.user

        if user.role not in [
            self.PARENT_USER,
            self.USER_ADMIN,
        ]:
            return error_response(
                message="you don't have the permission to add tank",
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = createTankSerislizer(
            data=request.data,
            context={
                "request": request
            }
        )

        if not serializer.is_valid():

            return error_response(
                message="Invalid data",
                data=serializer.errors,
                status=status.HTTP_400_BAD_REQUEST,
            )

        tank = serializer.save()

        return success_response(
            message="Tank added successfully.",
            data={
                "id": tank.id, 
                "name": tank.name
            }, 
            status=status.HTTP_201_CREATED,
        )