# Database

MySQL/MariaDB dump for the **Hermes AI Agent** system.

## File

| File | Description |
| --- | --- |
| `bsitcrud.sql` | Full dump of the `bsitcrud` database — schema plus data |

## Contents

12 tables:

**Application tables**

| Table | Description |
| --- | --- |
| `tblinfo` | Personal information records |
| `tblnewsarticle` | Cached AI news articles |

**Django built-in tables**

| Table | Description |
| --- | --- |
| `auth_user` | User accounts |
| `auth_group` | User groups |
| `auth_permission` | Permissions |
| `auth_group_permissions` | Group → permission links |
| `auth_user_groups` | User → group links |
| `auth_user_user_permissions` | User → permission links |
| `django_admin_log` | Admin action log |
| `django_content_type` | Model registry |
| `django_migrations` | Applied migrations |
| `django_session` | User sessions |

## Importing

### Option 1 — Import the dump directly

```bash
mysql -u root -e "CREATE DATABASE bsitcrud CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
mysql -u root bsitcrud < sql/bsitcrud.sql
```

### Option 2 — Create the schema from migrations

Use this if you would rather start with an empty database:

```bash
mysql -u root -e "CREATE DATABASE bsitcrud CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
python manage.py migrate
python manage.py createsuperuser
```

## Exporting a fresh dump

After making schema or data changes, regenerate the dump with:

```bash
mysqldump -u root --routines --events --single-transaction \
  --default-character-set=utf8mb4 bsitcrud > sql/bsitcrud.sql
```

On Windows (PowerShell), use `--result-file` instead of `>`. PowerShell's
redirect writes UTF-16, which corrupts the dump:

```powershell
& "D:\xampp\mysql\bin\mysqldump.exe" -u root --routines --events `
  --single-transaction --default-character-set=utf8mb4 `
  --result-file="sql\bsitcrud.sql" bsitcrud
```

## Note on credentials

The dump contains user accounts with **hashed** passwords (Django's PBKDF2
hasher), not plain text. It also includes session rows. For a public
repository this is generally fine, but if you would rather not publish
account data, use Option 2 above and keep the dump local.
