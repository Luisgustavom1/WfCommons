#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (c) 2020-2022 The WfCommons Team.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import logging
import uuid

from abc import ABC, abstractmethod
from os import path
from logging import Logger
from typing import Any, Dict, List, Optional

from wfcommons.common.file import File, FileLink
from wfcommons.common.task import Task, TaskType
from wfcommons.common.workflow import Workflow
from wfcommons.utils import generate_rvs


class WorkflowRecipe(ABC):
    """
    An abstract class of workflow recipes for creating synthetic workflow instances.

    :param name: The workflow recipe name.
    :type name: str
    :param data_footprint: The upper bound for the workflow total data footprint (in bytes).
    :type data_footprint: Optional[int]
    :param num_tasks: The upper bound for the total number of tasks in the workflow.
    :type num_tasks: Optional[int]
    :param runtime_factor: The factor of which tasks runtime will be increased/decreased.
    :type runtime_factor: Optional[float]
    :param input_file_size_factor: The factor of which tasks input files size will be increased/decreased.
    :type input_file_size_factor: Optional[float]
    :param output_file_size_factor: The factor of which tasks output files size will be increased/decreased.
    :type output_file_size_factor: Optional[float]
    :param logger: The logger where to log information/warning or errors (optional).
    :type logger: Optional[Logger]
    """

    def __init__(self, name: str,
                 data_footprint: Optional[int],
                 num_tasks: Optional[int],
                 runtime_factor: Optional[float] = 1.0,
                 input_file_size_factor: Optional[float] = 1.0,
                 output_file_size_factor: Optional[float] = 1.0,
                 logger: Optional[Logger] = None) -> None:
        """Create an object of the workflow recipe."""
        # sanity checks
        if runtime_factor <= 0.0:
            raise ValueError("The runtime factor should be a number higher than 0.0.")
        if input_file_size_factor <= 0.0:
            raise ValueError("The input file size factor should be a number higher than 0.0.")
        if output_file_size_factor <= 0.0:
            raise ValueError("The output file size factor should be a number higher than 0.0.")

        self.logger: Optional[Logger] = logging.getLogger(__name__) if logger is None else logger
        self.name = name
        self.data_footprint: Optional[int] = data_footprint
        self.num_tasks: Optional[int] = num_tasks
        self.runtime_factor: Optional[float] = runtime_factor
        self.input_file_size_factor: Optional[float] = input_file_size_factor
        self.output_file_size_factor: Optional[float] = output_file_size_factor
        self.workflow_recipe = None
        self.tasks_files: Dict[str, List[File]] = {}
        self.tasks_files_names: Dict[str, List[str]] = {}
        self.task_id_counter: int = 1
        self.tasks_map = {}
        self.tasks_children = {}
        self.tasks_parents = {}
        self.tasks_output_files = {}

    @abstractmethod
    def _workflow_recipe(self) -> Dict[str, Any]:
        """
        Recipe for generating synthetic instances for a workflow. Recipes can be
        generated by using the :class:`~wfcommons.wfinstances.instance_analyzer.InstanceAnalyzer`.

        :return: A recipe in the form of a dictionary in which keys are task prefixes.
        :rtype: Dict[str, Any]
        """
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def from_num_tasks(cls,
                       num_tasks: int,
                       runtime_factor: Optional[float] = 1.0,
                       input_file_size_factor: Optional[float] = 1.0,
                       output_file_size_factor: Optional[float] = 1.0
                       ) -> 'WorkflowRecipe':
        """
        Instantiate a workflow recipe that will generate synthetic workflows up to the
        total number of tasks provided.

        :param num_tasks: The upper bound for the total number of tasks in the workflow.
        :type num_tasks: int
        :param runtime_factor: The factor of which tasks runtime will be increased/decreased.
        :type runtime_factor: Optional[float]
        :param input_file_size_factor: The factor of which tasks input files size will be increased/decreased.
        :type input_file_size_factor: Optional[float]
        :param output_file_size_factor: The factor of which tasks output files size will be increased/decreased.
        :type output_file_size_factor: Optional[float]

        :return: A workflow recipe object that will generate synthetic workflows up to
                 the total number of tasks provided.
        :rtype: WorkflowRecipe
        """
        raise NotImplementedError

    @abstractmethod
    def build_workflow(self, workflow_name: Optional[str] = None) -> Workflow:
        """
        Generate a synthetic workflow instance.

        :param workflow_name: The workflow name
        :type workflow_name: Optional[str]

        :return: A synthetic workflow instance object.
        :rtype: Workflow
        """
        raise NotImplementedError

    def _generate_task(self, task_name: str, task_id: str) -> Task:
        """
        Generate a synthetic task.

        :param task_name: task name.
        :type task_name: str
        :param task_id: task ID.
        :type task_id: str

        :return: A task object.
        :rtype: task
        """
        task_recipe = self._workflow_recipe()[task_name]
        # runtime
        runtime: float = float(format(
            self.runtime_factor * generate_rvs(task_recipe['runtime']['distribution'],
                                               task_recipe['runtime']['min'],
                                               task_recipe['runtime']['max']), '.3f'))

        # # linking previous generated output files as input files
        self.tasks_files[task_id] = []
        self.tasks_files_names[task_id] = []
        task = Task(
            name=task_id,
            task_id='0{}'.format(task_id.split('_0')[1]),
            category=task_name,
            task_type=TaskType.COMPUTE,
            runtime=runtime,
            machine=None,
            program=task_name,
            args=[],
            cores=1,
            avg_cpu=None,
            bytes_read=None,
            bytes_written=None,
            memory=None,
            energy=None,
            avg_power=None,
            priority=None,
            files=[]
        )
        self.tasks_map[task_id] = task

        return task

    def _generate_task_name(self, prefix: str) -> str:
        """
        Generate a task name from a prefix appended with an ID.

        :param prefix: task prefix.
        :type prefix: str

        :return: task name from prefix appended with an ID.
        :rtype: str
        """
        task_name = "{}_{:08d}".format(prefix, self.task_id_counter)
        self.task_id_counter += 1
        return task_name

    def _generate_task_files(self, task: Task) -> List[File]:
        """
        Generate input and output files for a task.

        :param task: task object.
        :type task: Task

        :return: List of files output files.
        :rtype: List[File]
        """
        if task.name in self.tasks_output_files.keys():
            return self.tasks_output_files[task.name]

        task_recipe = self._workflow_recipe()[task.category]

        # generate output files
        output_files_list = self._generate_files(task.name, task_recipe['output'], FileLink.OUTPUT)
        task.files = self.tasks_files[task.name]

        # obtain input files from parents
        input_files = []
        if task.name in self.tasks_parents.keys():
            for parent_task_name in self.tasks_parents[task.name]:
                output_files = self._generate_task_files(self.tasks_map[parent_task_name])
                self.tasks_output_files.setdefault(parent_task_name, [])
                self.tasks_output_files[parent_task_name] = output_files
                input_files.extend(output_files)

        for input_file in input_files:
            if input_file.name not in self.tasks_files_names[task.name]:
                self.tasks_files[task.name].append(File(name=input_file.name,
                                                        link=FileLink.INPUT,
                                                        size=input_file.size))
                self.tasks_files_names[task.name].append(input_file.name)

        # generate additional input files
        self._generate_files(task.name, task_recipe['input'], FileLink.INPUT)

        return output_files_list

    def _generate_files(self, task_id: str, recipe: Dict[str, Any], link: FileLink) -> List[File]:
        """
        Generate files for a specific task ID.

        :param task_id: task ID.
        :type task_id: str
        :param recipe: Recipe for generating the task.
        :type recipe: Dict[str, Any]
        :param link: Type of file link.
        :type link: FileLink

        :return: List of files.
        :rtype: List[File]
        """
        files_list = []
        extension_list: List[str] = []
        for f in self.tasks_files[task_id]:
            if f.link == link:
                files_list.append(f)
                extension_list.append(path.splitext(f.name)[1] if '.' in f.name else f.name)

        for extension in recipe:
            if extension not in extension_list:
                file = self._generate_file(extension, recipe, link)
                files_list.append(file)
                self.tasks_files[task_id].append(file)
                self.tasks_files_names[task_id].append(file.name)

        return files_list

    def _generate_file(self, extension: str, recipe: Dict[str, Any], link: FileLink) -> File:
        """
        Generate a file according to a file recipe.

        :param extension:
        :type extension: str
        :param recipe: Recipe for generating the file.
        :type recipe: Dict[str, Any]
        :param link: Type of file link.
        :type link: FileLink

        :return: The generated file.
        :rtype: File
        """
        size = int((self.input_file_size_factor if link == FileLink.INPUT
                    else self.output_file_size_factor) * generate_rvs(recipe[extension]['distribution'],
                                                                      recipe[extension]['min'],
                                                                      recipe[extension]['max']))
        return File(name=str(uuid.uuid4()) + extension,
                    link=link,
                    size=size)

    def _get_files_by_task_and_link(self, task_id: str, link: FileLink) -> List[File]:
        """
        Get the list of files for a task ID and link type.

        :param task_id: task ID.
        :type task_id: str
        :param link: Type of file link.
        :type link: FileLink

        :return: List of files for a task ID and link type.
        :rtype: List[File]
        """
        files_list: List[File] = []
        for f in self.tasks_files[task_id]:
            if f.link == link:
                files_list.append(f)
        return files_list
