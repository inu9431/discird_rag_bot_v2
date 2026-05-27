from django.db import migrations
from pgvector.django import VectorExtension, VectorField, IvfflatIndex


class Migration(migrations.Migration):

    dependencies = [
        ("archiver", "0003_remove_category_choices"),
    ]

    operations = [
        VectorExtension(),
        migrations.AddField(
            model_name="qnalog",
            name="embedding",
            field=VectorField(dimensions=1536, null=True, blank=True),
        ),
        migrations.AddIndex(
            model_name="qnalog",
            index=IvfflatIndex(
                fields=["embedding"],
                name="qna_embedding_ivfflat_idx",
                lists=100,
            ),
        ),
    ]
