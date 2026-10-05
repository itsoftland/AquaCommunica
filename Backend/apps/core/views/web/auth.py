from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny


from apps.core.serializers.auth import LoginSerializer



class LoginView(APIView):

    permission_classes = [AllowAny, ]

    def post(self, request):

        serilalizer = LoginSerializer(
            data=request.data,
            context={"request": request},
        )

        serilalizer.is_valid(raise_exception=True)

        data = serilalizer.validated_data

        user = data["user"]

        user_details = {
            "id": user.id,
            "email": user.email,
            "role": user.role,
            "is_verified": user.is_verified,
        }


        return Response(
            {
                "message": "Login successful",

                "user": user_details,

                "tokens": {
                    "refresh": data["refresh"],
                    "access": data["access"],
                },
            },
            status=status.HTTP_200_OK,
        )
        