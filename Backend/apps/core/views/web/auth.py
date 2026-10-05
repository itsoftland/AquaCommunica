from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated


from apps.core.serializers.auth import LoginSerializer, UserRegisterSerializer, LogoutSerializer



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



class ProfileView(APIView):

    permission_classes = [IsAuthenticated,]

    def get(self, request):

        user = request.user

        user_details = {
            "id": user.id,
            "email": user.email,
            "role": user.role,
            "is_verified": user.is_verified,
        }

        return Response(
            {
                "message": "You are authenticated",
                "user": user_details,
            },
            status=status.HTTP_200_OK,
        )



class UserRegisterView(APIView):

    permission_classes = [AllowAny, ]

    def post(self, request):

        data = request.data

        serializer = UserRegisterSerializer(
            data=data
        )

        serializer.is_valid(raise_exception=True)

        user = serializer.save()

        return Response(
            {
                "message": "user created successfully.",
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "role": user.role,
                    "is_verified": user.is_verified,
                }
            },
            status=status.HTTP_201_CREATED,
        )



class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {
                "message": "Logout successful."
            },
            status=status.HTTP_200_OK
        )