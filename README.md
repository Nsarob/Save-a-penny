# Save-a-Penny

A mini **Procure-to-Pay** system built with Django REST Framework, featuring multi-level approval workflows, AI-powered document processing, and role-based access control.

##  Features

- **Multi-level Approval Workflow**: Staff submit requests → Level 1 & Level 2 approvers review → Automatic PO generation
- **Role-based Access Control**: Staff, Approver Level 1, Approver Level 2, and Finance roles
- **Document Processing (AI)**:
  - Proforma invoice extraction
  - Automatic Purchase Order generation
  - Receipt validation against PO
- **RESTful API**: Built with Django REST Framework
- **JWT Authentication**: Secure token-based authentication
- **API Documentation**: Swagger/ReDoc integration

##  Project Structure

```
Save-a-penny/
├── backend/                    # Django REST API
│   ├── core/                  # Project settings
│   ├── purchase_requests/     # Main app
│   │   ├── models.py         # Database models
│   │   ├── serializers.py    # DRF serializers
│   │   ├── views.py          # API views
│   │   └── urls.py           # API routes
│   ├── requirements.txt      # Python dependencies
│   ├── .env.example         # Environment template
│   └── manage.py
└── README.md
```

##  Prerequisites

- Python 3.11+
- PostgreSQL 14+ (or SQLite for development)
- Conda environment (named `flight`)

##  Setup Instructions

### 1. Clone the Repository

```bash
git clone https://github.com/Nsarob/Save-a-penny.git
cd Save-a-penny
```

### 2. Backend Setup

```bash
cd backend

# Activate conda environment
conda activate flight

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Edit .env with your configuration

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Run development server
python manage.py runserver
```

### 3. Access the Application

- **API Base URL**: http://localhost:8000/api/
- **Admin Panel**: http://localhost:8000/admin/
- **Swagger Docs**: http://localhost:8000/swagger/
- **ReDoc**: http://localhost:8000/redoc/

##  Authentication Endpoints

| Method | Endpoint                   | Description              |
| ------ | -------------------------- | ------------------------ |
| POST   | `/api/auth/register/`      | Register new user        |
| POST   | `/api/auth/login/`         | Login user               |
| POST   | `/api/auth/logout/`        | Logout user              |
| POST   | `/api/auth/token/refresh/` | Refresh access token     |
| GET    | `/api/auth/profile/`       | Get current user profile |

## 👥 User Roles

1. **Staff**: Create and manage their own purchase requests
2. **Approver Level 1**: Review and approve/reject requests (first level)
3. **Approver Level 2**: Review and approve/reject requests (second level)
4. **Finance**: View and interact with approved requests

##  Database Models

- **UserProfile**: Extended user with role information
- **PurchaseRequest**: Main request entity
- **Approval**: Multi-level approval tracking
- **RequestItem**: Line items for requests

##  Development Status

###  Phase 1: Project Foundation (Current)

- [x] Django project setup
- [x] Database models
- [x] JWT authentication
- [x] User registration/login
- [x] Basic API structure

###  Upcoming Phases

- Phase 2: Core API endpoints (Staff, Approver, Finance)
- Phase 3: Document processing (AI features)
- Phase 4: Dockerization
- Phase 5: Frontend (React)
- Phase 6: Deployment

##  Environment Variables

```env
SECRET_KEY=your-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

DB_NAME=save_a_penny
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=localhost
DB_PORT=5432

CORS_ORIGINS=http://localhost:3000
OPENAI_API_KEY=your-openai-key
```

##  Contributing

This is a step-by-step build with clean commit history. Each phase is committed separately.

##  License

MIT License

##  Author

Nsarob
