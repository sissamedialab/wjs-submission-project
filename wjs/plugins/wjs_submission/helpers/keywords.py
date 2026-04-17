from django.db import transaction
from journal.models import Journal
from submission.models import Keyword, KeywordGroup


def import_keywords_from_wjapp(journal_code: str, clear_existing: bool, dry_run: bool, data: list[dict]):
    journal = Journal.objects.get(code=journal_code)
    # Use transaction to ensure atomicity
    with transaction.atomic():
        # Create a savepoint for dry-run rollback
        sid = transaction.savepoint()

        try:
            # Clear existing data if requested
            if clear_existing and not dry_run:
                groups = list(
                    KeywordGroup.objects.filter(keywords__journal=journal).values_list("pk", flat=True).distinct()
                )
                parent_groups = list(
                    KeywordGroup.objects.filter(keywordgroup__pk__in=groups).values_list("pk", flat=True).distinct()
                )
                Keyword.objects.filter(journal=journal).delete()
                KeywordGroup.objects.filter(pk__in=groups).delete()
                KeywordGroup.objects.filter(pk__in=parent_groups).delete()

            # Statistics counters
            groups_created = 0
            subgroups_created = 0
            keywords_created = 0
            keywords_skipped = 0

            # Process each main group
            for group_order, group_data in enumerate(data, start=1):
                group_name = group_data.get("group", "")
                subgroups = group_data.get("subgroups", {})

                # Create main group
                main_group, created = KeywordGroup.objects.get_or_create(
                    name=group_name,
                    defaults={
                        "parent_group": None,
                        "order": group_order,
                        "notes": f"Main group for {group_name}",
                    },
                )

                if created:
                    groups_created += 1

                # Process subgroups and their keywords
                for subgroup_order, (subgroup_name, keywords) in enumerate(subgroups.items(), start=1):
                    if subgroup_name:
                        # Create subgroup
                        subgroup, created = KeywordGroup.objects.get_or_create(
                            name=subgroup_name,
                            parent_group=main_group,
                            defaults={
                                "order": subgroup_order,
                                "notes": f"Subgroup under {group_name}",
                            },
                        )

                        if created:
                            subgroups_created += 1
                        notes = (f"Keyword in {subgroup_name} under {group_name}",)
                    else:
                        subgroup = main_group
                        notes = (f"Keyword in {group_name}",)

                    # Create keywords for this subgroup
                    for keyword_text in keywords:
                        keyword_text = keyword_text.strip()  # noqa: PLW2901
                        if not keyword_text:
                            continue

                        try:
                            keyword, created = Keyword.objects.get_or_create(
                                word=keyword_text,
                                defaults={
                                    "group": subgroup,
                                    "notes": notes,
                                },
                            )
                            journal.keywords.add(keyword)

                            if created:
                                keywords_created += 1
                            else:
                                keywords_skipped += 1

                        except Exception:  # noqa: BLE001, S112
                            continue

            # Rollback if dry-run
            if dry_run:
                transaction.savepoint_rollback(sid)
            else:
                transaction.savepoint_commit(sid)

        except Exception:
            transaction.savepoint_rollback(sid)
            raise

    # Print final database statistics
    if not dry_run:
        total_groups = KeywordGroup.objects.count()
        total_keywords = Keyword.objects.count()
        return {
            "total_groups": total_groups,
            "total_keywords": total_keywords,
            "groups_created": groups_created,
            "subgroups_created": subgroups_created,
            "keywords_created": keywords_created,
            "keywords_skipped": keywords_skipped,
        }
    return None
