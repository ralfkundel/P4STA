# Copyright 2019-present Ralf Kundel, Fridolin Siegmund
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include

import management_ui.views_dir.analyze as analyze
import management_ui.views_dir.configure as configure
import management_ui.views_dir.deploy as deploy
import management_ui.views_dir.run as run
import management_ui.views_dir.setup_devices as setup_devices

from management_ui import globals

# initialize global used variables
globals.main()


# 'job_' => does not render html template but returns json
urlpatterns = [
    # base path returns configuration page
    path('', configure.configure_page, name='index'),

    # main pages
    path('analyze/', analyze.page_analyze),
    path('configuration/', configure.configure_page),
    path('deploy/', deploy.page_deploy),
    path('run/', run.page_run),
    path('setup_devices/', setup_devices.setup_devices),

    # helper functions for setup_devices
    path('skip_setup_redirect_to_config/', setup_devices.
         skip_setup_redirect_to_config),
    path('run_setup_script/', setup_devices.run_setup_script),
    path('stop_shellinabox_redirect_to_config/',
         setup_devices.stop_shellinabox_redirect_to_config),

    # non-ajax related GET or POST's (e.g. <a> or form submit)
    path('deleteData/', analyze.delete_data),
    path('downloadAllResults/', analyze.download_all_zip),
    path('downloadExtResults/', analyze.download_external_results),
    path('downloadLoadgenResults/', analyze.download_loadgen_results),
    path('downloadStamperResults/', analyze.download_stamper_results),
    path('createConfig/', configure.create_new_cfg_from_template),
    path('openConfig/', configure.open_selected_config),
    path('deleteConfig/', configure.delete_selected_config),
    path('saveConfig/', configure.save_config_as_file),

    # ajax
    # page_analyze.html
    path('subpage_analyze_external_results/', analyze.external_results),
    path('subpage_analyze_loadgen_results/', run.read_loadgen_results_again),
    path('subpage_analyze_stamper_results/', analyze.stamper_results),

    # page_config.html
    path('job_fetch_iface/', configure.fetch_iface),
    path('job_set_iface/', configure.set_iface),
    # also used in output_external_started.html
    path('status_overview/', configure.status_overview),

    # page_deploy.html
    path('subpage_deploy_stamper_status/', deploy.stamper_status),
    path('subpage_deploy_stop_stamper_software/',
         deploy.stop_stamper_software),

    # page_run.html
    path('subpage_run_ping/', run.ping),
    path('subpage_run_start_external/', run.start_external),
    path('subpage_run_stop_external/', run.stop_external),

    # setup_page.html
    path('job_setup_ssh_checker/', setup_devices.setup_ssh_checker),

    # output_external_started.html
    path('subpage_run_run_loadgens/', run.run_loadgens_first),

    # page_deploy.html => output_stamper_software_status.html
    path('subpage_deploy_deploy_device/', deploy.deploy),
    path('subpage_deploy_show_ports/', deploy.stamper_ports),
    path('subpage_deploy_host_iface_status/', deploy.host_iface_status),
    path('subpage_deploy_start_stamper_software/',
         deploy.start_stamper_software),
    path('subpage_deploy_get_stamper_startup_log/',
         deploy.get_stamper_startup_log),
    path('subpage_deploy_reboot/', deploy.reboot),
    path('subpage_deploy_refresh_links/', deploy.refresh_links),

    # page_run.html => output_external_started.html
    path('subpage_run_reset/', run.reset),

    # output_status_overview.html
    path('job_delete_namespace/', configure.delete_namespace),

    # output_external_results.html
    path('dygraph/', analyze.dygraph)

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
