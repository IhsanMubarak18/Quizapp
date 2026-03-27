# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('video_app', '0004_auto_20260314_1546'),
    ]

    operations = [
        migrations.AddField(
            model_name='quiz',
            name='max_attempts',
            field=models.PositiveIntegerField(default=0, help_text='Maximum attempts per student (0 for unlimited)'),
        ),
    ]
