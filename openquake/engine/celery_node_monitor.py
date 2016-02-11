#  -*- coding: utf-8 -*-
#  vim: tabstop=4 shiftwidth=4 softtabstop=4

#  Copyright (c) 2014-2016, GEM Foundation

#  OpenQuake is free software: you can redistribute it and/or modify it
#  under the terms of the GNU Affero General Public License as published
#  by the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.

#  OpenQuake is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.

#  You should have received a copy of the GNU Affero General Public License
#  along with OpenQuake.  If not, see <http://www.gnu.org/licenses/>.

import os
import sys
import time
import signal
import threading

import celery.task.control

from openquake.engine import logs
from openquake.engine.utils import config
from openquake.commonlib.valid import boolean
from openquake.commonlib.oqvalidation import OqParam

USE_CELERY = boolean(config.get('celery', 'use_celery'))


class MasterKilled(KeyboardInterrupt):
    """
    Exception raised when a job is killed manually or aborted
    by the `openquake.engine.engine.CeleryNodeMonitor`.
    """
    registered_handlers = False  # set when the signal handlers are registered

    @classmethod
    def handle_signal(cls, signum, _stack):
        """
        When a SIGTERM or a SIGABRT is received, raise the MasterKilled
        exception with an appropriate error message.

        :param int signum: the number of the received signal
        :param _stack: the current frame object, ignored
        """
        if signum == signal.SIGTERM:
            msg = 'The openquake master process was killed manually'
        elif signum == signal.SIGABRT:
            msg = ('The openquake master process was killed by the '
                   'CeleryNodeMonitor because some node failed')
        else:
            msg = 'This should never happen'
        raise cls(msg)

    @classmethod
    def register_handlers(cls):
        """
        Register the signal handlers for SIGTERM and SIGABRT
        if they were not registered before.
        """
        if not cls.registered_handlers:  # called only once
            signal.signal(signal.SIGTERM, cls.handle_signal)
            signal.signal(signal.SIGABRT, cls.handle_signal)
            cls.registered_handlers = True


class CeleryNodeMonitor(object):
    """
    Context manager wrapping a block of code with a monitor thread
    checking that the celery nodes are accessible. The check is
    performed periodically by pinging the nodes. If some node fail,
    for instance due to an out of memory error, a SIGABRT signal
    is sent to the master process.

    :param float interval:
        polling interval in seconds
    :param bool no_distribute:
        if True, the CeleryNodeMonitor will do nothing at all
    """
    def __init__(self, no_distribute, interval, use_celery=USE_CELERY):
        self.no_distribute = no_distribute
        self.interval = interval
        self.use_celery = use_celery
        self.job_running = True
        self.live_nodes = None  # set of live worker nodes
        self.th = None
        MasterKilled.register_handlers()

    # this is called only is use_celery is True
    def set_concurrent_tasks_default(self):
        """
        Set the default for concurrent_tasks to twice the number of workers.
        Returns the number of live celery nodes (i.e. the number of machines).
        """
        stats = celery.task.control.inspect(timeout=1).stats()
        if not stats:
            sys.exit("No live compute nodes, aborting calculation")
        num_workers = sum(stats[k]['pool']['max-concurrency'] for k in stats)
        OqParam.concurrent_tasks.default = 2 * num_workers
        return set(stats)

    def __enter__(self):
        if self.no_distribute:
            return self  # do nothing
        elif self.use_celery:
            self.live_nodes = self.set_concurrent_tasks_default()
            self.th = threading.Thread(None, self.check_nodes)
            self.th.start()
        return self

    def __exit__(self, etype, exc, tb):
        self.job_running = False
        if self.th:
            self.th.join()

    # this is called only is use_celery is True
    def ping(self, timeout):
        """
        Ping the celery nodes by using .interval as timeout parameter
        """
        celery_inspect = celery.task.control.inspect(timeout=timeout)
        try:
            response_dict = celery_inspect.ping() or {}
        except Exception as e:
            logs.LOG.warn(str(e))
            response_dict = {}
        return set(response_dict)

    def check_nodes(self):
        """
        Check that the expected celery nodes are all up. The loop
        continues until the main thread keeps running.
        """
        while self.job_is_running(sleep=self.interval):
            live_nodes = self.ping(timeout=self.interval)
            if live_nodes < self.live_nodes:
                dead_nodes = list(self.live_nodes - live_nodes)
                logs.LOG.warn(
                    'Workers not accessible: %s', dead_nodes)
                logs.LOG.warn(
                    'If celery died, please stop the calculation '
                    'with CTRL-C or kill %s', os.getpid())

    def job_is_running(self, sleep):
        """
        Check for 10 times during the sleep interval if the flag
        self.job_running becomes false and then exit.
        """
        for _ in range(10):
            if not self.job_running:
                break
            time.sleep(sleep / 10.)
        return self.job_running
