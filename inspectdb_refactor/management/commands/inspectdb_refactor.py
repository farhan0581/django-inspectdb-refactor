import keyword
import re
from collections import OrderedDict
import os
from django.core.management.base import BaseCommand, CommandError
from django.db import DEFAULT_DB_ALIAS, connections
from django.db.models.constants import LOOKUP_SEP
from django.conf import settings
from django.core.management.commands.inspectdb import Command as InspectbCommand


class Command(InspectbCommand):
    help = ("Introspects the database tables in the given "
            "database and makes models, views, admin and forms files.")

    missing_args_message = (
        "No app label provided. Please provide app label for path."
    )

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)
        parser.add_argument(
            '--app', action='store', dest='app',
            help='Needs app lablel to identify path to create modules.',
        )

    def make_dirs(self, app_path):
        '''
           creates models, views, admin and forms
           folder and empty files, except for models.    
        '''
        modules_path = {}
        dirs_to_make = ['models', 'admin', 'views', 'forms']
        self.init_file = '__init__.py'

        for module in dirs_to_make:
            dir_path = ("%s/%s") % (app_path, module)
            
            # check if dir exists
            if not os.path.exists(dir_path):
                try:
                    original_umask = os.umask(0)
                    os.makedirs(dir_path, 0o777)
                finally:
                    os.umask(original_umask)
            init_file_path = ("%s/%s")%(dir_path, self.init_file)

            # check if file exists
            if not os.path.exists(init_file_path):
                open(init_file_path, 'w').close()
            modules_path[module] = dir_path

        self.modules_path= modules_path

    def make_file(self, table_name):
        '''
           makes different files(models, views, admin and forms)
           in the concerned directories
        '''
        model_file = ''
        for module, path in self.modules_path.items():

            if module == 'admin':
                file_name = "%s_admin.py" % table_name 
            elif module == 'views':
                file_name = "%s_view.py" % table_name
            elif module == 'forms':
                file_name = "%s_form.py" % table_name
            else:
                file_name = "%s.py" % table_name
                model_file = "%s/%s" % (path, file_name)

            path = ("%s/%s") % (path, file_name)

            if not os.path.exists(path):
                open(path, 'w').close()
        return model_file


    def handle(self, **options):
        try:
            self.handle_inspection(options)
        except NotImplementedError:
            raise CommandError("Database inspection isn't supported for the currently selected database backend.")

    def handle_inspection(self, options):
        connection = connections[options['database']]
        # 'table_name_filter' is a stealth option
        table_name_filter = options.get('table_name_filter')

        def table2model(table_name):
            return re.sub(r'[^a-zA-Z0-9]', '', table_name.title())

        def strip_prefix(s):
            return s[1:] if s.startswith("u'") else s
        
        app_label = options.get('app')
        app_path = ("%s/%s") % (settings.BASE_DIR, app_label)

        self.make_dirs(app_path)
        models_init_file_code = ''
        models_init_file = ("%s/%s") % (self.modules_path['models'], self.init_file) 
        handle_model_init_file = open(models_init_file, 'w')

        with connection.cursor() as cursor:
            known_models = []
            tables_to_introspect = options['table'] or connection.introspection.table_names(cursor)

            for table_name in tables_to_introspect:

                model_file = self.make_file(table_name)

                handle = open(model_file, 'w')

                file_code = ''

                models_init_file_code += "from %s.models.%s import %s\n" % (
                                            
                                app_label, model_file.split("/")[-1].split(".")[0], table2model(table_name)
                            )


                file_code +=  'from %s import models\n' % self.db_module

                if table_name_filter is not None and callable(table_name_filter):
                    if not table_name_filter(table_name):
                        continue
                try:
                    try:
                        relations = connection.introspection.get_relations(cursor, table_name)
                    except NotImplementedError:
                        relations = {}
                    try:
                        constraints = connection.introspection.get_constraints(cursor, table_name)
                    except NotImplementedError:
                        constraints = {}
                    primary_key_column = connection.introspection.get_primary_key_column(cursor, table_name)
                    unique_columns = [
                        c['columns'][0] for c in constraints.values()
                        if c['unique'] and len(c['columns']) == 1
                    ]
                    table_description = connection.introspection.get_table_description(cursor, table_name)
                except Exception as e:
                    file_code +=  "# Unable to inspect table '%s'" % table_name
                    file_code +=  "# The error was: %s" % e
                    continue

                file_code +=  '\n'
                file_code +=  '\n'
                file_code +=  'class %s(models.Model):\n' % table2model(table_name)
                known_models.append(table2model(table_name))
                used_column_names = []  # Holds column names used in the table so far
                column_to_field_name = {}  # Maps column names to names of model fields
                for row in table_description:
                    comment_notes = []  # Holds Field notes, to be displayed in a Python comment.
                    extra_params = OrderedDict()  # Holds Field parameters such as 'db_column'.
                    column_name = row[0]
                    is_relation = column_name in relations

                    att_name, params, notes = self.normalize_col_name(
                        column_name, used_column_names, is_relation)
                    extra_params.update(params)
                    comment_notes.extend(notes)

                    used_column_names.append(att_name)
                    column_to_field_name[column_name] = att_name

                    # Add primary_key and unique, if necessary.
                    if column_name == primary_key_column:
                        extra_params['primary_key'] = True
                    elif column_name in unique_columns:
                        extra_params['unique'] = True

                    if is_relation:
                        rel_to = (
                            "self" if relations[column_name][1] == table_name
                            else table2model(relations[column_name][1])
                        )
                        field_type = "ForeignKey('%s'" % rel_to
                    else:
                        # Calling `get_field_type` to get the field type string and any
                        # additional parameters and notes.
                        field_type, field_params, field_notes = self.get_field_type(connection, table_name, row)
                        extra_params.update(field_params)
                        comment_notes.extend(field_notes)

                        field_type += '('

                    # Don't output 'id = meta.AutoField(primary_key=True)', because
                    # that's assumed if it doesn't exist.
                    if att_name == 'id' and extra_params == {'primary_key': True}:
                        if field_type == 'AutoField(':
                            continue
                        elif field_type == 'IntegerField(' and not connection.features.can_introspect_autofield:
                            comment_notes.append('AutoField?')

                    # Add 'null' and 'blank', if the 'null_ok' flag was present in the
                    # table description.
                    if row[6]:  # If it's NULL...
                        if field_type == 'BooleanField(':
                            field_type = 'NullBooleanField('
                        else:
                            extra_params['blank'] = True
                            extra_params['null'] = True

                    field_desc = '%s = %s%s' % (
                        att_name,
                        # Custom fields will have a dotted path
                        '' if '.' in field_type else 'models.',
                        field_type,
                    )
                    if field_type.startswith('ForeignKey('):
                        field_desc += ', models.DO_NOTHING'

                    if extra_params:
                        if not field_desc.endswith('('):
                            field_desc += ', '
                        field_desc += ', '.join(
                            '%s=%s' % (k, strip_prefix(repr(v)))
                            for k, v in extra_params.items())
                    field_desc += ')'
                    if comment_notes:
                        field_desc += '  # ' + ' '.join(comment_notes)
                    file_code +=  '    %s\n' % field_desc
                for meta_line in self.get_meta(table_name, constraints, column_to_field_name):
                    file_code +=  "%s\n" % (meta_line)
                    
                handle.write(file_code)

        # models init file code        
        handle_model_init_file.write(models_init_file_code)
