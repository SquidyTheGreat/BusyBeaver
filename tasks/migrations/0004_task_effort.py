from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0003_eventlog'),
    ]

    operations = [
        migrations.AddField(
            model_name='task',
            name='effort',
            field=models.DurationField(blank=True, null=True),
        ),
    ]
