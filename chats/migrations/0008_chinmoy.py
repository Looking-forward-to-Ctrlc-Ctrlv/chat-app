# Generated by Django 5.2 on 2025-04-30 05:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chats', '0007_chatfile'),
    ]

    operations = [
        migrations.CreateModel(
            name='Chinmoy',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('Name', models.CharField(default='Chinmoy', max_length=50)),
            ],
        ),
    ]
