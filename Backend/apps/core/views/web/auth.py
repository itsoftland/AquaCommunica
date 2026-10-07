from rest_framework.views import APIView
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated


from ...utlis.responses import success_response
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


        return success_response(
            "Login successful",
            {
                "user": user_details,
                "tokens": {
                    "refresh": data["refresh"],
                    "access": data["access"],
                },
            },
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

        return success_response(
            "You are authenticated",
            {"user": user_details},
        )



class UserRegisterView(APIView):

    permission_classes = [IsAuthenticated, ]

    def post(self, request):

        data = request.data

        serializer = UserRegisterSerializer(
            data=data,
            context={"request": request},
        )

        serializer.is_valid(raise_exception=True)

        user = serializer.save()

        return success_response(
            "User created successfully.",
            {
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "role": user.role,
                    "is_verified": user.is_verified,
                    "created_by": user.created_by.email,
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

        return success_response("Logout successful.")