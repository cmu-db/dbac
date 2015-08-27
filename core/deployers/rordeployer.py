import os, sys
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

import logging
import re
import traceback
import MySQLdb

from basedeployer import BaseDeployer
from crawler.models import *
import utils

## =====================================================================
## LOGGING CONFIGURATION
## =====================================================================
LOG = logging.getLogger()

## =====================================================================
## SETTINGS
## =====================================================================
DATABASE_SETTINGS = """
development:
  adapter: mysql2
  database: {}
  pool: 5
  timeout: 5000
  username: root
  password: root
  shost: localhost

test:
  adapter: mysql2
  database: {}
  pool: 5
  timeout: 5000
  username: root
  password: root
  shost: localhost

production:
  adapter: mysql2
  database: {}
  pool: 5
  timeout: 5000
  username: root
  password: root
  shost: localhost
"""

GEMFILE_SETTINGS = """
gem 'mysql2'
"""

## =====================================================================
## RUBY ON RAILS DEPLOYER
## =====================================================================
class RoRDeployer(BaseDeployer):
    def __init__(self, repo, database):
        BaseDeployer.__init__(self, repo, database)
        self.database_name = 'ror_app'
        self.setting_path = None
    ## DEF
    
    # TODO : fix
    def get_database(self, settings_file):
        db = Database.objects.get(name__iexact="sqlite3")
        return db
    ## DEF

    def extract_database_info(self):
        try:
            conn = MySQLdb.connect(host='localhost',user='root',passwd='root',db=self.database_name, port=3306)
            cur = conn.cursor()
            cur.close()
            conn.close()
        except:
            print traceback.print_exc()
    ## DEF
    
    def configure_settings(self):
        with open(os.path.join(self.setting_path, 'config/database.yml'), "w") as my_file:
            my_file.write(DATABASE_SETTINGS.format(self.database_name, self.database_name, self.database_name))
        ## WITH
        with open(os.path.join(self.setting_path, 'Gemfile'), "a") as my_file:
            my_file.write(GEMFILE_SETTINGS)
        ## WITH
    ## DEF
    
    def install_requirements(self, path):
        if path:
            command = '{} && bundle install'.format(utils.cd(path))
            out = utils.run_command(command)
            return out
        return []
    ## DEF
    
    def get_urls(self):
        return ['']
    ## DEF

    def sync_server(self, path):
        LOG.info('Syncing server ...')
        command = '{} && bundle exec rake db:migrate'.format(utils.cd(path))
        return utils.run_command(command)
    ## DEF

    def run_server(self, path):
        LOG.info('Running server ...')
        command = '{} && bundle exec rails server -p {} -d'.format(
            utils.cd(path), 
            self.repo.project_type.default_port)
        return utils.run_command(command)
    ## DEF

    def try_deploy(self, attempt, deploy_path):
        LOG.info('Configuring settings ...')
        self.kill_server()
        self.clear_database()
        self.configure_settings()
        
        LOG.info('Installing requirements ...')
        out = self.install_requirements(deploy_path)
        LOG.info(out)
        if not 'complete!' in out[1]:
            return ATTEMPT_STATUS_MISSING_DEPENDENCIES

        out = self.sync_server(deploy_path)
        LOG.info(out)
        if "rake aborted!" in out[1]:
            return ATTEMPT_STATUS_RUNNING_ERROR
        
        out = self.run_server(deploy_path)
        LOG.info(out)

        attemptStatus = self.check_server(self.get_urls())

        return attemptStatus

    ## DEF
    
    def deploy_repo_attempt(self, attempt, deploy_path):
        rakefiles = utils.search_file(deploy_path, 'Rakefile')
        if not rakefiles:
            LOG.error('No rakefile found!')
            return ATTEMPT_STATUS_MISSING_REQUIRED_FILES
        rakefile_paths = [os.path.dirname(rakefile) for rakefile in rakefiles]
        

        gemfiles = utils.search_file(deploy_path, 'Gemfile')
        if not gemfiles:
            LOG.error('No gemfile found!')
            return ATTEMPT_STATUS_MISSING_REQUIRED_FILES
        gemfile_paths = [os.path.dirname(gemfile) for gemfile in gemfiles]

        db_files = utils.search_file(deploy_path, 'database.yml')
        if not db_files:
            LOG.error("Unable to find database.yml")
            return ATTEMPT_STATUS_MISSING_REQUIRED_FILES
        db_file_paths = [os.path.dirname(os.path.dirname(db_file)) for db_file in db_files if os.path.basename(os.path.normpath(os.path.dirname(db_file))) == "config"]
        
        base_dirs = set.intersection(set(rakefile_paths), set(gemfile_paths), set(db_file_paths))
        if not base_dirs:
            LOG.error('Can not find base directory!')
            return ATTEMPT_STATUS_MISSING_REQUIRED_FILES
        base_dir = next(iter(base_dirs))

        self.setting_path = base_dir

        attempt.base_dir = base_dir.split('/', 1)[1]
        # LOG.info('BASE_DIR: ' + attempt.base_dir)

        attempt.database = self.get_database(os.path.join(base_dir, 'config/database.yml'))
        # LOG.info('Database: ' + attempt.database.name)

        return self.try_deploy(attempt, base_dir)
    ## DEF
    
## CLASS