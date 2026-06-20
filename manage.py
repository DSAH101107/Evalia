#!/usr/bin/env python
import os, sys
try:
    import pymysql
    pymysql.install_as_MySQLdb()
except ModuleNotFoundError:
    pass

def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)
if __name__ == '__main__':
    main()
