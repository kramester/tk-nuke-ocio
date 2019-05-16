# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
OCIO handling for Nuke

"""

import os
import nuke
import tank
from tank import TankError


class NukeOCIONode(tank.platform.Application):

    def init_app(self):
        """
        Called as the application is being initialized
        """

        # this app should not do anything if nuke is run without gui.

        if nuke.env['gui']:
            # first deal with nuke root settings: we don't need a context for this

            self.log_debug("Loading tk-nuke-ocio app for a gui session.")

            self._setOCIOConfigContext()
            self._setOCIOKnobDefaults()  # if I don't do this and do a File/New in Nuke, the new instance of nuke does not set the OCIO settings on the root node.
            self._add_root_callbacks()

            self._setOCIOSettingsOnRootNode()
            self._setOCIODisplayContext()
            self._add_callbacks()

        else:
            self.log_debug("Loading tk-nuke-ocio app for a non-gui session.")
            self._setOCIOConfigContext()

    def destroy_app(self):
        """
        Called when the app is unloaded/destroyed
        """
        self.log_debug("Destroying tk-nuke-ocio app")

        # remove any callbacks that were registered by the handler:
        self._remove_root_callbacks()
        self._remove_callbacks()

    def _resolve_template(self, template, context, fields=None):
        """Resolves sgtk templates.

        Uses the current context to resolve an sgtk template.

        :param str template: template name defined in templates.yml
        :param dict fields: extra fields that cannot be resolved by context alone.
        :return: A resolved sgtk template
        :rtype: str
        """

        tmpl = self.sgtk.templates[template]
        flds = context.as_template_fields(tmpl, validate=True)

        if fields is not None:
            flds.update(flds)

        return tmpl.apply_fields(flds)

    def _setOCIOConfigContext(self):

        current_context = self.context

        if current_context:
            env_vars = {
                "PROJECT": None,
                "SHOT": None,
                "SEQUENCE": None,
                "OCIO_CONFIG": None,
                "LUT": None,
                "LOOK": None,
            }

            seq_color_config = None
            shot_color_config = None
            project_color_config = None
            current_color_config = None

            # Sets the SEQUENCE and SHOT env vars
            if current_context.entity:
                type = current_context.entity['type']
                id = current_context.entity['id']
                entity = current_context.sgtk.shotgun.find_one(type, [['id', 'is', id]], ['code', 'sg_sequence', 'sg_color_config'])
                if type == "Sequence":
                    env_vars["SEQUENCE"] = entity.get('sg_sequence').get('name')
                    seq_color_config = entity.get("sg_color_config")
                if type == "Shot":
                    seq_id = entity.get('sg_sequence').get('id')
                    env_vars["SEQUENCE"] = entity.get('sg_sequence').get('name')
                    env_vars["SHOT"] = entity.get("code")
                    shot_color_config = entity.get("sg_color_config")
                    seq_entity = current_context.sgtk.shotgun.find_one('Sequence', [['id', 'is', seq_id]], ['code', 'sg_color_config'])
                    seq_color_config = seq_entity.get("sg_color_config")

            # Sets the PROJECT env var
            if current_context.project:
                id = current_context.project['id']
                entity = current_context.sgtk.shotgun.find_one('Project', [['id', 'is', id]], ['code', 'sg_color_config'])
                env_vars["PROJECT"] = entity['code']
                project_color_config = entity.get("sg_color_config")

            if project_color_config:
                current_color_config = project_color_config
            if seq_color_config:
                current_color_config = seq_color_config
            if shot_color_config:
                current_color_config = shot_color_config

            if current_color_config:
                color = current_context.sgtk.shotgun.find_one('CustomNonProjectEntity06', [['id', 'is', current_color_config['id']]], ['code', 'sg_ocio_config', 'sg_sequence_look', 'sg_shot_look', 'sg_project_lut'])
                env_vars["OCIO_CONFIG"] = os.path.join(self._resolve_template("ocio_config_path", current_context), color.get("sg_ocio_config"))
                env_vars["LOOK"] = color.get("sg_shot_look")
                env_vars["LUT"] = color.get("sg_project_lut")

            for key, value in env_vars.iteritems():
                if not value:
                    if os.environ.get(key):
                        self.log_debug("Clearing ENV variable: {}".format(key))
                        os.environ.pop(key)
                else:
                    self.log_debug("Setting ENV variable: {} = {}".format(key, value))
                    os.environ[key] = value

    def _add_root_callbacks(self):
        """
        Add callbacks to watch for certain events:
        """

        nuke.addOnCreate(self._setOCIOSettingsOnRootNode, nodeClass='Root')

    def _remove_root_callbacks(self):
        """
        Removed previously added callbacks
        """
        nuke.removeOnCreate(self._setOCIOSettingsOnRootNode, nodeClass='Root')

    def _add_callbacks(self):
        """
        Add callbacks to watch for certain events:
        """

        nuke.addOnCreate(self._setOCIODisplayContext, nodeClass="OCIODisplay")

    def _remove_callbacks(self):
        """
        Removed previously added callbacks
        """
        nuke.removeOnCreate(self._setOCIODisplayContext, nodeClass="OCIODisplay")

    def _setOCIODisplayContext(self):

        listVP = nuke.ViewerProcess.registeredNames()
        viewers = nuke.allNodes('Viewer')

        for v in viewers:
            for l in listVP:
                if nuke.ViewerProcess.node(l, v['name'].value()):
                    if nuke.ViewerProcess.node(l)['key1'].value() != 'SEQUENCE':
                        nuke.ViewerProcess.node(l)['key1'].setValue('SEQUENCE')
                    if nuke.ViewerProcess.node(l)['value1'].value() != os.getenv("SEQUENCE"):
                        nuke.ViewerProcess.node(l)['value1'].setValue(os.getenv("SEQUENCE"))
                    if nuke.ViewerProcess.node(l)['key2'].value() != 'SHOT':
                        nuke.ViewerProcess.node(l)['key2'].setValue('SHOT')
                    if nuke.ViewerProcess.node(l)['value2'].value() != os.getenv("SHOT"):
                        nuke.ViewerProcess.node(l)['value2'].setValue(os.getenv("SHOT"))
                    if nuke.ViewerProcess.node(l)['key3'].value() != 'LOOK':
                        nuke.ViewerProcess.node(l)['key3'].setValue('LOOK')
                    if nuke.ViewerProcess.node(l)['value3'].value() != os.getenv("LOOK"):
                        nuke.ViewerProcess.node(l)['value3'].setValue(os.getenv("LOOK"))
                    if nuke.ViewerProcess.node(l)['key4'].value() != 'LUT':
                        nuke.ViewerProcess.node(l)['key4'].setValue('LUT')
                    if nuke.ViewerProcess.node(l)['value4'].value() != os.getenv("LUT"):
                        nuke.ViewerProcess.node(l)['value4'].setValue(os.getenv("LUT"))

    def _setOCIOSettingsOnRootNode(self):

        ocio_path = os.getenv("OCIO_CONFIG")
        ocio_path = ocio_path.replace(os.path.sep, "/")
        ocio_path = nuke.filenameFilter(ocio_path)

        colorManagementKnob = nuke.root().knob("colorManagement")
        OCIOconfigKnob = nuke.root().knob("OCIO_config")
        customOCIOConfigPathKnob = nuke.root().knob("customOCIOConfigPath")

        # If this is a new script, then set the knobs. This may seem redundant given that we also
        # set knob defaults, but nuke seems to need both to correctly load the
        # viewer processes.
        if nuke.root().knob("name").value() == '':
            # Set the color management to Nuke first. Setting it from 'Nuke'
            # to 'OCIO' seems to be what initializes the viewer processes.
            self.log_debug("New script detected, setting Root node OCIO settings.")
            colorManagementKnob.setValue("Nuke")
            OCIOconfigKnob.setValue("custom")
            customOCIOConfigPathKnob.setValue(ocio_path)
            colorManagementKnob.setValue("OCIO")
        # for an existing script, check the settings and ask the user to change if incorrect
        elif colorManagementKnob.value() == 'OCIO' and \
          OCIOconfigKnob.value() == 'custom' and \
          customOCIOConfigPathKnob.value() == ocio_path:
            pass
        else:
            self.log_debug("Preseting user with dialog...")
            anwser = nuke.ask('WARNING: Your OCIO settings do not match the correct settings for this project<p> \
                Nuke is currently using the %s OCIO config located in:<br><i>%s</i><p>\
                It is supposed to use the custom OCIO config for this project located in:<br><i>%s</i><p>\
                Do you want me to correct the OCIO settings?<br>Please be aware that changing the OCIO config \
                is going to reset all ocio nodes.' % (OCIOconfigKnob.value(), customOCIOConfigPathKnob.value(), ocio_path))
            if anwser:
                self.log_debug("User accepted changes, setting Root node OCIO settings.")
                colorManagementKnob.setValue("Nuke")
                OCIOconfigKnob.setValue("custom")
                customOCIOConfigPathKnob.setValue(ocio_path)
                colorManagementKnob.setValue("OCIO")
            else:
                self.log_debug("User refused, keeping current Root node OCIO settings.")

    def _setOCIOKnobDefaults(self):

        # Knob defaults by themselves dont seem to work correctly, they dont
        # intialize the viewer processes so we're also hitting this with
        # a big stick in the _setOCIOSettingsOnRootNode function and
        # essentially setting these defaults twice. Yay Nuke!

        ocio_path = os.getenv("OCIO_CONFIG")
        ocio_path = ocio_path.replace(os.path.sep, "/")
        ocio_path = nuke.filenameFilter(ocio_path)

        self.log_debug("Setting knob defaults for Root node OCIO settings.")
        nuke.knobDefault("Root.colorManagement", "OCIO")
        nuke.knobDefault("Root.OCIO_config", "custom")
        nuke.knobDefault("Root.customOCIOConfigPath", ocio_path)
