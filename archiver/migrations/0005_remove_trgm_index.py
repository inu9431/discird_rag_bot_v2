from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("archiver", "0004_add_embedding"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="qnalog",
            name="qna_question_tgrm_idx",
        ),
    ]
