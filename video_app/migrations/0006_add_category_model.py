# Generated migration for Category model and Question category field
from django.db import migrations, models
import django.db.models.deletion


def create_default_category(apps, schema_editor):
    """Create a default category for existing questions."""
    Category = apps.get_model('video_app', 'Category')
    Category.objects.get_or_create(
        name='General',
        defaults={
            'description': 'Default category for uncategorized questions',
            'is_active': True
        }
    )


def assign_default_category_to_questions(apps, schema_editor):
    """Assign default category to all existing questions."""
    Category = apps.get_model('video_app', 'Category')
    Question = apps.get_model('video_app', 'Question')
    
    default_category = Category.objects.get(name='General')
    Question.objects.filter(category__isnull=True).update(category=default_category)


class Migration(migrations.Migration):

    dependencies = [
        ('video_app', '0005_quiz_max_attempts'),
    ]

    operations = [
        # Create Category model
        migrations.CreateModel(
            name='Category',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('description', models.TextField(blank=True, help_text='Optional description of the category')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('is_active', models.BooleanField(default=True)),
            ],
            options={
                'verbose_name_plural': 'Categories',
                'ordering': ['name'],
            },
        ),
        
        # Add category field to Question (nullable initially)
        migrations.AddField(
            model_name='question',
            name='category',
            field=models.ForeignKey(
                null=True, 
                on_delete=django.db.models.deletion.CASCADE, 
                to='video_app.category', 
                help_text='Select the category for this question'
            ),
        ),
        
        # Create a default category
        migrations.RunPython(
            create_default_category,
            reverse_code=migrations.RunPython.noop
        ),
        
        # Update existing questions to use default category
        migrations.RunPython(
            assign_default_category_to_questions,
            reverse_code=migrations.RunPython.noop
        ),
        
        # Make category field required
        migrations.AlterField(
            model_name='question',
            name='category',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, 
                to='video_app.category', 
                help_text='Select the category for this question'
            ),
        ),
    ]
