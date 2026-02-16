---
description: Django Best Practices (HackSoftware Styleguide)
alwaysApply: true
applyTo: "**/*.py"
---

# Django Reference (HackSoftware Styleguide)

- [Official Styleguide](https://github.com/HackSoftware/Django-Styleguide)
- [Example Project](https://github.com/HackSoftware/django-styleguide-example)

## Core Principles

1.  **Separation of Concerns**:
    -   **Business Logic** -> `services.py`
    -   **Data Retrieval** -> `selectors.py`
    -   **Data Schema** -> `models.py`
    -   **HTTP/Input/Output** -> `apis.py`
2.  **Explicit is better than Implicit**:
    -   No Model signals for business logic.
    -   No Model overrides (`save()`) for business logic.
    -   No Magic.
3.  **Fat Services, Thin Components**:
    -   Views should only validate input and call services.
    -   Models should only define data structure.
4.  **Testing**:
    -   Focus on **Service Tests**.
    -   Use Factories (`factory_boy`).

## Project Structure

A modular structure is preferred. Each logical component is an "app".

```text
project_root/
  common/             # Shared utilities, base models
    models.py
    utils.py
    exceptions.py
  users/              # App: Users
    models.py         # Data definitions only
    services.py       # Actions (Create, Update, Delete, Auth)
    selectors.py      # Queries (List, Detail, Filter)
    apis.py           # DRF Views (Input/Output protocols)
    urls.py           # Routing
    tests/            # App-specific tests
      services/
      selectors/
      apis/
  payments/           # App: Payments
    ...
```

## Models (`models.py`)

Models are the **Data Schema**. They should be "dumb".

### Rules
-   **No Business Logic**: Never put logic in `save()` or custom methods that do more than compute properties.
-   **No Signals**: Do not use `post_save` or `pre_save` for business logic (e.g., sending emails). Use Service orchestration instead.
-   **Base Model**: Inherit from a shared `BaseModel`.

### Example
```python
# common/models.py
from django.db import models
import uuid

class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

# users/models.py
class User(BaseModel):
    email = models.EmailField(unique=True)
    is_admin = models.BooleanField(default=False)
    
    def __str__(self):
        return self.email
```

## Services (`services.py`)

Services are the **Business Logic**. They **do** things.

### Rules
-   **Function-Based**: Use simple functions. Classes are overkill for most logic.
-   **Naming**: `<entity>_<action>` (e.g., `user_create`, `user_update`).
-   **Transactions**: Decorate with `@transaction.atomic` if multiple writes occur.
-   **Explicit Arguments**: No `**kwargs`. Define every argument. Type hints are mandatory.
-   **Return**: The main object created or updated.

### Pattern: Create Service
```python
from django.db import transaction
from common.services import model_update

@transaction.atomic
def user_create(*, email: str, password: str) -> User:
    user = User(email=email)
    user.set_password(password)
    user.full_clean()  # Validate model fields
    user.save()
    
    # Side effects (e.g., email) belong here, explicitly called
    # email_send_welcome(user=user)
    
    return user
```

### Pattern: Update Service
Use a generic `model_update` utility to handle partial updates cleanly.

```python
# common/services.py
def model_update(*, instance, fields: list[str], data: dict[str, Any]) -> Any:
    has_updated = False
    for field in fields:
        if field in data:
            setattr(instance, field, data[field])
            has_updated = True
    
    if has_updated:
        instance.full_clean()
        instance.save(update_fields=fields)
    
    return instance

# users/services.py
def user_update(*, user: User, data: dict[str, Any]) -> User:
    # Whitelist allowed fields
    fields = ["is_admin", "email"]
    
    user, has_updated = model_update(
        instance=user,
        fields=fields,
        data=data
    )
    
    return user
```

## Selectors (`selectors.py`)

Selectors are the **Read Layer**. They **fetch** things.

### Rules
-   **Side-Effect Free**: Never change data in a selector.
-   **Input**: Filter arguments.
-   **Output**: `QuerySet`, `List`, or simple Objects.
-   **Optimization**: Use `select_related` and `prefetch_related` here.

### Example
```python
def user_list(*, filters: dict = None) -> QuerySet[User]:
    filters = filters or {}
    qs = User.objects.all()
    
    if "email_contains" in filters:
        qs = qs.filter(email__icontains=filters["email_contains"])
        
    if "is_admin" in filters:
        qs = qs.filter(is_admin=filters["is_admin"])
        
    return qs

def user_get(*, id: str) -> User | None:
    return User.objects.filter(id=id).first()
```

## APIs (`apis.py`)

APIs are the **Interface**. They **translate** HTTP to Services.

### Rules
-   **Framework**: Use Django Rest Framework (DRF).
-   **Views**: `APIView` (simple, explicit) > `GenericAPIView` > `ViewSet` (too much magic).
-   **Serializers**:
    -   **InputSerializer**: Validates request data.
    -   **OutputSerializer**: Formats response data.
    -   **No Logic**: Do not use `serializer.save()`.

### Pattern: Create API
```python
from rest_framework import serializers, status
from rest_framework.views import APIView
from rest_framework.response import Response

class UserCreateApi(APIView):
    class InputSerializer(serializers.Serializer):
        email = serializers.EmailField()
        password = serializers.CharField()

    class OutputSerializer(serializers.ModelSerializer):
        class Meta:
            model = User
            fields = ("id", "email", "created_at")

    def post(self, request):
        serializer = self.InputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Call Service
        user = user_create(**serializer.validated_data)
        
        # Format Response
        return Response(
            self.OutputSerializer(user).data, 
            status=status.HTTP_201_CREATED
        )
```

### Pattern: List API
```python
class UserListApi(APIView):
    class FilterSerializer(serializers.Serializer):
        email_contains = serializers.CharField(required=False)
        is_admin = serializers.BooleanField(required=False)

    class OutputSerializer(serializers.ModelSerializer):
        class Meta:
            model = User
            fields = ("id", "email")

    def get(self, request):
        filters_serializer = self.FilterSerializer(data=request.query_params)
        filters_serializer.is_valid(raise_exception=True)
        
        # Call Selector
        users = user_list(filters=filters_serializer.validated_data)
        
        return Response(self.OutputSerializer(users, many=True).data)
```

## Error Handling

### Service Domain Exceptions
Create specific exceptions for business logic failures.

```python
# common/exceptions.py
class ApplicationError(Exception):
    def __init__(self, message, code=None):
        super().__init__(message)
        self.message = message
        self.code = code

# users/services.py
def user_create(email, password):
    if User.objects.filter(email=email).exists():
        raise ApplicationError("User with this email already exists.")
```

### API Exception Handler
Catch domain exceptions globally and format them as HTTP responses.

```python
# project/urls.py or exception handler config
from rest_framework.views import exception_handler as drf_exception_handler

def custom_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    
    if response is None:
        if isinstance(exc, ApplicationError):
            return Response(
                {"detail": exc.message}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
    return response
```

## Testing

Tests ensure reliability.

### 1. Factories (`make_*.py` or `factories.py`)
Use `factory_boy` to create test data.

```python
import factory
from .models import User

class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
    
    email = factory.Faker("email")
```

### 2. Service Tests (Primary)
Test the logic directly. Fast and focused.

```python
from django.test import TestCase
from users.services import user_create

class UserCreateServiceTests(TestCase):
    def test_creates_user_correctly(self):
        user = user_create(email="test@example.com", password="password")
        self.assertEqual(user.email, "test@example.com")
        self.assertTrue(user.check_password("password"))

    def test_raises_error_if_email_exists(self):
        user_create(email="test@example.com", password="123")
        with self.assertRaises(ApplicationError):
            user_create(email="test@example.com", password="456")
```

### 3. API Tests (Integration)
Test the HTTP layer. Verify status codes and serialization.

```python
from django.urls import reverse
from rest_framework.test import APITestCase

class UserCreateApiTests(APITestCase):
    def test_api_creates_user(self):
        url = reverse("user-create")
        data = {"email": "api@test.com", "password": "pass"}
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["email"], "api@test.com")
```

## Golden Rules Recap

1.  **Do not use Model Serializers for Write Operations**. They mix validation with logic. Use standard `Serializer` for input.
2.  **Avoid Circular Imports**. Models is the lowest layer. Services depend on Models. APIs depend on Services.
3.  **One URL, One Action**. Avoid RESTful generic viewsets that try to do everything (List/Create/Detail/Update/Delete) in one class unless it's a very simple CRUD. Explicit `UserCreateApi` is better than `UserViewSet`.
4.  **Static Types**. Use Python type hints aggressively.
5.  **Validation**. Logic validation (e.g. "is this user active?") goes in Service. Data validation (e.g. "is this an email?") goes in Serializer/Layer.
