# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models


class AuthGroup(models.Model):
    name = models.CharField(unique=True, max_length=150)

    class Meta:
        managed = False
        db_table = 'auth_group'


class AuthGroupPermissions(models.Model):
    id = models.BigAutoField(primary_key=True)
    group = models.ForeignKey(AuthGroup, models.DO_NOTHING)
    permission = models.ForeignKey('AuthPermission', models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'auth_group_permissions'
        unique_together = (('group', 'permission'),)


class AuthPermission(models.Model):
    name = models.CharField(max_length=255)
    content_type = models.ForeignKey('DjangoContentType', models.DO_NOTHING)
    codename = models.CharField(max_length=100)

    class Meta:
        managed = False
        db_table = 'auth_permission'
        unique_together = (('content_type', 'codename'),)


class AuthUser(models.Model):
    password = models.CharField(max_length=128)
    last_login = models.DateTimeField(blank=True, null=True)
    is_superuser = models.BooleanField()
    username = models.CharField(unique=True, max_length=150)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    email = models.CharField(max_length=254)
    is_staff = models.BooleanField()
    is_active = models.BooleanField()
    date_joined = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'auth_user'


class AuthUserGroups(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(AuthUser, models.DO_NOTHING)
    group = models.ForeignKey(AuthGroup, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'auth_user_groups'
        unique_together = (('user', 'group'),)


class AuthUserUserPermissions(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(AuthUser, models.DO_NOTHING)
    permission = models.ForeignKey(AuthPermission, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'auth_user_user_permissions'
        unique_together = (('user', 'permission'),)


class DimLocation(models.Model):
    location_id = models.CharField(primary_key=True, max_length=5)
    zip_code_prefix = models.CharField(max_length=5, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=5, blank=True, null=True)
    latitude = models.FloatField(blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'dim_location'


class DimSeller(models.Model):
    seller_id = models.CharField(primary_key=True, max_length=50)
    location = models.ForeignKey(DimLocation, models.DO_NOTHING, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=5, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'dim_seller'


class DimProduct(models.Model):
    product_id = models.CharField(primary_key=True, max_length=50)
    category_name_english = models.CharField(max_length=100, blank=True, null=True)
    weight_g = models.FloatField(blank=True, null=True)
    volume_cm3 = models.FloatField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'dim_product'


class DimTime(models.Model):
    time_id = models.IntegerField(primary_key=True)
    full_date = models.DateField()
    month = models.IntegerField(blank=True, null=True)
    year = models.IntegerField(blank=True, null=True)
    quarter = models.IntegerField(blank=True, null=True)
    day_of_week = models.CharField(max_length=15, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'dim_time'


class DjangoAdminLog(models.Model):
    action_time = models.DateTimeField()
    object_id = models.TextField(blank=True, null=True)
    object_repr = models.CharField(max_length=200)
    action_flag = models.SmallIntegerField()
    change_message = models.TextField()
    content_type = models.ForeignKey('DjangoContentType', models.DO_NOTHING, blank=True, null=True)
    user = models.ForeignKey(AuthUser, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'django_admin_log'


class DjangoContentType(models.Model):
    app_label = models.CharField(max_length=100)
    model = models.CharField(max_length=100)

    class Meta:
        managed = False
        db_table = 'django_content_type'
        unique_together = (('app_label', 'model'),)


class DjangoMigrations(models.Model):
    id = models.BigAutoField(primary_key=True)
    app = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    applied = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'django_migrations'


class DjangoSession(models.Model):
    session_key = models.CharField(primary_key=True, max_length=40)
    session_data = models.TextField()
    expire_date = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'django_session'


class FactDeliverySla(models.Model):
    pk = models.CompositePrimaryKey('order_id', 'order_item_id')
    order_id = models.CharField(max_length=50)
    order_item_id = models.IntegerField()
    product = models.ForeignKey(DimProduct, models.DO_NOTHING, blank=True, null=True)
    seller = models.ForeignKey(DimSeller, models.DO_NOTHING, blank=True, null=True)
    customer_location = models.ForeignKey(DimLocation, models.DO_NOTHING, blank=True, null=True)
    seller_location = models.ForeignKey(DimLocation, models.DO_NOTHING, related_name='factdeliverysla_seller_location_set', blank=True, null=True)
    time = models.ForeignKey(DimTime, models.DO_NOTHING, blank=True, null=True)
    payment_type = models.CharField(max_length=50, blank=True, null=True)
    price = models.FloatField(blank=True, null=True)
    freight_value = models.FloatField(blank=True, null=True)
    shipping_limit_date = models.DateTimeField(blank=True, null=True)
    approval_time_days = models.FloatField(blank=True, null=True)
    seller_prep_time_days = models.FloatField(blank=True, null=True)
    carrier_transit_time_days = models.FloatField(blank=True, null=True)
    delay_days = models.FloatField(blank=True, null=True)
    total_lead_days = models.FloatField(blank=True, null=True)
    promise_days = models.FloatField(blank=True, null=True)
    handoff_slack_days = models.FloatField(blank=True, null=True)
    distance_km = models.FloatField(blank=True, null=True)
    review_score = models.IntegerField(blank=True, null=True)
    has_logistics_complaint = models.BooleanField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'fact_delivery_sla'
