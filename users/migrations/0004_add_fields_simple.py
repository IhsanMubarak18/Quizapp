# Simple migration to add qualification and district fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0002_auto_20260314_1546'),
    ]

    operations = [
        # Add new qualification and district fields
        migrations.AddField(
            model_name='studentprofile',
            name='qualification',
            field=models.CharField(max_length=50, choices=[
                ('SSLC', 'SSLC'),
                ('Plus Two', 'Plus Two'),
                ('Degree', 'Degree'),
                ('Others', 'Others')
            ], default='SSLC'),
        ),
        migrations.AddField(
            model_name='studentprofile',
            name='qualification_other',
            field=models.CharField(max_length=200, blank=True, null=True),
        ),
        migrations.AddField(
            model_name='studentprofile',
            name='district',
            field=models.CharField(max_length=100, choices=[
                ('Thiruvananthapuram', 'Thiruvananthapuram'),
                ('Kollam', 'Kollam'),
                ('Pathanamthitta', 'Pathanamthitta'),
                ('Alappuzha', 'Alappuzha'),
                ('Kottayam', 'Kottayam'),
                ('Idukki', 'Idukki'),
                ('Ernakulam', 'Ernakulam'),
                ('Thrissur', 'Thrissur'),
                ('Palakkad', 'Palakkad'),
                ('Malappuram', 'Malappuram'),
                ('Kozhikode', 'Kozhikode'),
                ('Wayanad', 'Wayanad'),
                ('Kannur', 'Kannur'),
                ('Kasaragod', 'Kasaragod'),
                ('Others', 'Others')
            ], default='Ernakulam'),
        ),
        migrations.AddField(
            model_name='studentprofile',
            name='district_other',
            field=models.CharField(max_length=200, blank=True, null=True),
        ),
    ]
