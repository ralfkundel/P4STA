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

from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from . import views

urlpatterns = [
    path('', views.configure_page, name='index'),
    path('setup_devices/', views.setup_devices),
    path('skip_setup_redirect_to_config/', views.skip_setup_redirect_to_config),
    path('run_setup_script/', views.run_setup_script),
    path('stop_shellinabox_redirect_to_config/', views.stop_shellinabox_redirect_to_config),
    path('setup_ssh_checker/', views.setup_ssh_checker),
    path('configuration/', views.configure_page),
    path('deploy/', views.page_deploy),
    path('run/', views.page_run),
    path('analyze/', views.page_analyze),
    path('run_loadgens/', views.run_loadgens_first),
    path('loadgen_results/', views.read_loadgen_results_again),
    path('deploy_device/', views.deploy),
    path('show_ports/', views.p4_dev_ports),
    path('host_iface_status/', views.host_iface_status),
    path('ping/', views.ping),
    path('p4_dev_results/', views.p4_dev_results),
    path('reset/', views.reset),
    path('p4_dev_status/', views.p4_dev_status),
    path('start_p4_dev_software/', views.start_p4_dev_software),
    path('get_p4_dev_startup_log/', views.get_p4_dev_startup_log),
    path('stop_p4_dev_software/', views.stop_p4_dev_software),
    path('reboot/', views.reboot),
    path('refresh_links/', views.refresh_links),
    path('startExternal/', views.start_external),
    path('stopExternal/', views.stop_external),
    path('externalResults/', views.external_results),
    path('downloadExtResults/', views.download_external_results),
    path('deleteData/', views.delete_data), #delete measurement on analyze page
    path('deleteNamespace/', views.delete_namespace),
    path('downloadSwitch/', views.download_p4_dev_results),
    path('downloadLoadgen/', views.download_loadgen_results),
    path('fetch_iface/', views.fetch_iface),
    path('set_iface/', views.set_iface),
    path('status_overview/', views.status_overview),
    path('createConfig/', views.create_new_cfg_from_template),
    path('openConfig/', views.open_selected_config),
    path('deleteConfig/', views.delete_selected_config),
    path('saveConfig/', views.save_config_as_file),
    path('dygraph/', views.dygraph)
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

