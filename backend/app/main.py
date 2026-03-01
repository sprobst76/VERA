from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import create_tables
from app.api.v1.auth import router as auth_router
from app.api.v1.employees import router as employees_router
from app.api.v1.shifts import shifts_router, templates_router
from app.api.v1.absences import employee_absences_router, care_absences_router
from app.api.v1.payroll import router as payroll_router
from app.api.v1.users import router as users_router
from app.api.v1.calendar import router as calendar_router, vacation_router
from app.api.v1.superadmin import router as superadmin_router
from app.api.v1.holiday_profiles import router as holiday_profiles_router
from app.api.v1.recurring_shifts import router as recurring_shifts_router
from app.api.v1.compliance import router as compliance_router
from app.api.v1.notifications import router as notifications_router
from app.api.v1.admin_settings import router as admin_settings_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Tabellen beim Start anlegen (SQLite / lokale Entwicklung)
    await create_tables()
    yield


app = FastAPI(
    title="VERA API",
    description="Verwaltung, Einsatz, Reporting & Assistenz",
    version="1.0.0",
    lifespan=lifespan,
    # Swagger UI nur in Entwicklung – in Produktion DEBUG=false setzen
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_PREFIX = "/api/v1"

app.include_router(auth_router, prefix=API_PREFIX)
app.include_router(employees_router, prefix=API_PREFIX)
app.include_router(shifts_router, prefix=API_PREFIX)
app.include_router(templates_router, prefix=API_PREFIX)
app.include_router(employee_absences_router, prefix=API_PREFIX)
app.include_router(care_absences_router, prefix=API_PREFIX)
app.include_router(payroll_router, prefix=API_PREFIX)
app.include_router(users_router, prefix=API_PREFIX)
app.include_router(superadmin_router, prefix=API_PREFIX)
app.include_router(holiday_profiles_router, prefix=API_PREFIX)
app.include_router(recurring_shifts_router, prefix=API_PREFIX)
app.include_router(vacation_router, prefix=API_PREFIX)
app.include_router(compliance_router, prefix=API_PREFIX)
app.include_router(notifications_router, prefix=API_PREFIX)
app.include_router(admin_settings_router, prefix=API_PREFIX)
app.include_router(calendar_router)  # public, no auth prefix


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "VERA API", "version": "1.0.0"}
