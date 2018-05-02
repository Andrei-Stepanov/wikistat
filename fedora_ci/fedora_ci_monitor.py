#!/usr/bin/env python2

# Use `env python2` for virtualenv

import argparse
import json
import time
import os
import re
import requests
import sys
import yaml

# This file chekcs ansible tags. standard-test-roles RPM should be installed.

requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)

"""
This scripts checks if Fedora CI pipeline executes correctly and branch has tests (/tests/tests.yml)
"""


JENKINS_URL = "https://jenkins-continuous-infra.apps.ci.centos.org"
DATAGREPPER_URL = "https://apps.fedoraproject.org/datagrepper/raw"

GIT_COMMIT_TOPIC = "org.fedoraproject.prod.git.receive"
NEW_PR_TOPIC = "org.fedoraproject.prod.pagure.pull-request.new"
NEW_PR_COMMENT_TOPIC = "org.fedoraproject.prod.pagure.pull-request.comment.added"
KOJIBUILD_TOPIC = "org.fedoraproject.prod.buildsys.build.state.change"

PR_PIPELINE_PKG_IGNORED_TOPIC = "org.centos.prod.ci.pipeline.allpackages-pr.package.ignored"
PR_PIPELINE_PKG_QUEUED_TOPIC = "org.centos.prod.ci.pipeline.allpackages-pr.package.queued"
PR_PIPELINE_PKG_RUNNING_TOPIC = "org.centos.prod.ci.pipeline.allpackages-pr.package.running"
PR_PIPELINE_PKG_COMPLETE_TOPIC = "org.centos.prod.ci.pipeline.allpackages-pr.package.complete"
PR_PIPELINE_IMG_QUEUED_TOPIC = "org.centos.prod.ci.pipeline.allpackages-pr.image.queued"
PR_PIPELINE_IMG_RUNNING_TOPIC = "org.centos.prod.ci.pipeline.allpackages-pr.image.running"
PR_PIPELINE_IMG_COMPLETE_TOPIC = "org.centos.prod.ci.pipeline.allpackages-pr.image.complete"
PR_PIPELINE_TESTS_QUEUED_TOPIC = "org.centos.prod.ci.pipeline.allpackages-pr.package.test.functional.queued"
PR_PIPELINE_TESTS_RUNNING_TOPIC = "org.centos.prod.ci.pipeline.allpackages-pr.package.test.functional.running"
PR_PIPELINE_TESTS_COMPLETE_TOPIC = "org.centos.prod.ci.pipeline.allpackages-pr.package.test.functional.complete"
PR_PIPELINE_COMPLETE_TOPIC = "org.centos.prod.ci.pipeline.allpackages-pr.complete"

BUILD_PIPELINE_PKG_IGNORED_TOPIC = "org.centos.prod.ci.pipeline.allpackages-build.package.ignored"
BUILD_PIPELINE_PKG_QUEUED_TOPIC = "org.centos.prod.ci.pipeline.allpackages-build.package.queued"
BUILD_PIPELINE_PKG_RUNNING_TOPIC = "org.centos.prod.ci.pipeline.allpackages-build.package.running"
BUILD_PIPELINE_PKG_COMPLETE_TOPIC = "org.centos.prod.ci.pipeline.allpackages-build.package.complete"
BUILD_PIPELINE_IMG_QUEUED_TOPIC = "org.centos.prod.ci.pipeline.allpackages-build.image.queued"
BUILD_PIPELINE_IMG_RUNNING_TOPIC = "org.centos.prod.ci.pipeline.allpackages-build.image.running"
BUILD_PIPELINE_IMG_COMPLETE_TOPIC = "org.centos.prod.ci.pipeline.allpackages-build.image.complete"
BUILD_PIPELINE_TESTS_QUEUED_TOPIC = "org.centos.prod.ci.pipeline.allpackages-build.package.test.functional.queued"
BUILD_PIPELINE_TESTS_RUNNING_TOPIC = "org.centos.prod.ci.pipeline.allpackages-build.package.test.functional.running"
BUILD_PIPELINE_TESTS_COMPLETE_TOPIC = "org.centos.prod.ci.pipeline.allpackages-build.package.test.functional.complete"
BUILD_PIPELINE_COMPLETE_TOPIC = "org.centos.prod.ci.pipeline.allpackages-build.complete"

VALID_PIPELINE_TOPICS = [PR_PIPELINE_PKG_QUEUED_TOPIC, PR_PIPELINE_PKG_RUNNING_TOPIC, PR_PIPELINE_PKG_COMPLETE_TOPIC,
                         PR_PIPELINE_IMG_QUEUED_TOPIC, PR_PIPELINE_IMG_RUNNING_TOPIC, PR_PIPELINE_IMG_COMPLETE_TOPIC,
                         PR_PIPELINE_TESTS_QUEUED_TOPIC, PR_PIPELINE_TESTS_RUNNING_TOPIC, PR_PIPELINE_TESTS_COMPLETE_TOPIC,
                         PR_PIPELINE_COMPLETE_TOPIC, PR_PIPELINE_PKG_IGNORED_TOPIC,
                         BUILD_PIPELINE_PKG_QUEUED_TOPIC, BUILD_PIPELINE_PKG_RUNNING_TOPIC, BUILD_PIPELINE_PKG_COMPLETE_TOPIC,
                         BUILD_PIPELINE_IMG_QUEUED_TOPIC, BUILD_PIPELINE_IMG_RUNNING_TOPIC, BUILD_PIPELINE_IMG_COMPLETE_TOPIC,
                         BUILD_PIPELINE_TESTS_QUEUED_TOPIC, BUILD_PIPELINE_TESTS_RUNNING_TOPIC, BUILD_PIPELINE_TESTS_COMPLETE_TOPIC,
                         BUILD_PIPELINE_COMPLETE_TOPIC, BUILD_PIPELINE_PKG_IGNORED_TOPIC]

PIPELINES = {"pr": "fedora-%s-pr-pipeline",
             "kojibuild": "fedora-%s-build-pipeline" }


PASS = 0
INFRA_FAILURE = 1
TEST_FAILURE = 2
SKIP = 3
RUNNING = 4


def _query_url(url):
    try:
        resp = requests.get(url, verify=False)
    except Exception as e:
        print("FAIL: Could not connect to %s" % url)
        print("Exception: %s" % e)
        return None
    if resp.status_code < 200 or resp.status_code >= 300:
        return None
    return resp.text


def check_tests(project, branch="master", pr=None):
    """
    Check if there is tests for given project/branch
    """
    if not project:
        return False

    if branch.lower() == "rawhide":
        branch = "master"

    repo = "https://src.fedoraproject.org/rpms/%s" % project
    if not pr:
        url = "%s/raw/%s/f/tests/tests.yml" % (repo, branch)
        if not _query_url(url):
            return False

    os.system('rm -rf %s' % project)
    os.system("git clone -b %s --single-branch %s" % (branch, repo))
#    os.system("cd %s && git checkout %s" % (project, branch))

    if pr:
        # apply the PR before checking if tests exist as PR could add tests
        os.system("curl https://src.fedoraproject.org/rpms/%s/pull-request/%s.patch > %s.patch" % (project, pr, pr))
        os.system("cd %s && git apply ../%s.patch" % (project, pr))
        os.system("rm -rf %s & rm -f %s" % (project, pr))

    if os.system("test -d %s/tests" % project) != 0:
        os.system("rm -rf %s & rm -f %s" % (project, pr))
        return False

    # Make sure test on branch can run on classic
    check_classic = 'ansible-playbook --list-tags tests.yml 2> /dev/null | grep -e "TASK TAGS: \[.*\\<classic\\>.*\]"'
    cmd = "cd %s/tests && %s" % (project, check_classic)
    has_tests = False
    if os.system(cmd) == 0:
        has_tests = True
    os.system('rm -rf %s' % project)

    return has_tests

def has_jenkins_pipeline(pipeline_type, branch):
    """
    Check if there is CI pipeline for specific branch
    """
    if branch == "master":
        branch = "rawhide"

    pipeline = PIPELINES[pipeline_type] % branch
    jenkins_query = "%s/view/all/job/%s/api/json?pretty=true" % (JENKINS_URL, pipeline)
    result = _query_url(jenkins_query)
    if not result:
        return False
    return True


def get_jenkins_build_info(pipeline_type, branch, build_id):
    if branch == "master":
        branch = "rawhide"

    pipeline = PIPELINES[pipeline_type] % branch
    jenkins_query = "%s/view/all/job/%s/%s/api/json?pretty=true" % (JENKINS_URL, pipeline, build_id)
    result = _query_url(jenkins_query)
    if not result:
        return None

    jresult = json.loads(result)
    return jresult


def get_jenkins_build(project, branch, commit_id):
    """
    Checks if there is a Jenkins build on proper Jenkins pipeline
    """

    if branch == "master":
        branch = "rawhide"

    print("INFO: Checking if tests there is build in Jenkins for %s %s %s" % (project, branch, commit_id))

    pipeline = PIPELINES[pipeline_type] % branch
    jenkins_query = "%s/view/all/job/%s/api/json?pretty=true" % (JENKINS_URL, pipeline)
    result = _query_url(jenkins_query)
    if not result:
        return None

    jresult = json.loads(result)
    builds = jresult['builds']
    if not builds:
        return None

    for build in builds:
        message_url = ("%s/view/all/job/%s/%s/artifact/messages/message-audit.json" %
                    (JENKINS_URL, pipeline, build['number']))
        result = _query_url(message_url)
        if not result:
            return None

        build_msgs = json.loads(result)
        for b_msg in build_msgs:
            msg = json.loads(build_msgs[b_msg])
            msg_repo = msg['repo']
            msg_branch = msg['branch']
            msg_rev = msg['rev']

            if msg_repo == project and msg_branch == branch and msg_rev == commit_id:
                return int(build['number'])

    return None

class Monitor:

    def __init__(self):
        # Check datagrepper messages from the last 24 hours
        self.delta = os.getenv("DELTA", 24*3600)
        # By default we wait for running builds on pipeline to complete
        self.wait_complete = True
        self.queried_topics = {}
        self.pipeline_steps = {}

        valid_status = {"SUCCESS": PASS, "FAILURE": INFRA_FAILURE, "UNSTABLE" : TEST_FAILURE}

        self.pipeline_steps["pr"] = [{"topic" : PR_PIPELINE_PKG_QUEUED_TOPIC, "timeout" : 2, "status" : valid_status},
                                     {"topic" : PR_PIPELINE_PKG_RUNNING_TOPIC, "timeout" : 10, "status" : valid_status},
                                     {"topic" : PR_PIPELINE_PKG_COMPLETE_TOPIC, "timeout" : 120, "status" : valid_status},
                                     {"topic" : PR_PIPELINE_IMG_QUEUED_TOPIC, "timeout" : 10, "status" : valid_status},
                                     {"topic" : PR_PIPELINE_IMG_RUNNING_TOPIC, "timeout" : 10, "status" : valid_status},
                                     {"topic" : PR_PIPELINE_IMG_COMPLETE_TOPIC, "timeout" : 60, "status" : valid_status},
                                     {"topic" : PR_PIPELINE_TESTS_QUEUED_TOPIC, "timeout" : 10, "status" : valid_status},
                                     {"topic" : PR_PIPELINE_TESTS_RUNNING_TOPIC, "timeout" : 10, "status" : valid_status},
                                     {"topic" : PR_PIPELINE_TESTS_COMPLETE_TOPIC, "timeout" : 5*60, "status" : valid_status},
                                     {"topic" : PR_PIPELINE_COMPLETE_TOPIC, "timeout" : 5, "status" : valid_status}]


        self.pipeline_steps["build"] = [{"topic" : BUILD_PIPELINE_PKG_QUEUED_TOPIC, "timeout" : 2, "status" : valid_status},
                                        {"topic" : BUILD_PIPELINE_PKG_RUNNING_TOPIC, "timeout" : 10, "status" : valid_status},
                                        {"topic" : BUILD_PIPELINE_PKG_COMPLETE_TOPIC, "timeout" : 10, "status" : valid_status},
                                        {"topic" : BUILD_PIPELINE_IMG_QUEUED_TOPIC, "timeout" : 10, "status" : valid_status},
                                        {"topic" : BUILD_PIPELINE_IMG_RUNNING_TOPIC, "timeout" : 10, "status" : valid_status},
                                        {"topic" : BUILD_PIPELINE_IMG_COMPLETE_TOPIC, "timeout" : 60, "status" : valid_status},
                                        {"topic" : BUILD_PIPELINE_TESTS_QUEUED_TOPIC, "timeout" : 10, "status" : valid_status},
                                        {"topic" : BUILD_PIPELINE_TESTS_RUNNING_TOPIC, "timeout" : 10, "status" : valid_status},
                                        {"topic" : BUILD_PIPELINE_TESTS_COMPLETE_TOPIC, "timeout" : 5*60, "status" : valid_status},
                                        {"topic" : BUILD_PIPELINE_COMPLETE_TOPIC, "timeout" : 5, "status" : valid_status}]

    def set_wait_complete(self, value):
        self.wait_complete = value

    def _query_datagrepper(self, topic):
        page=1
        pages=9999
        data = []

        if topic in self.queried_topics and not self.wait_complete:
            # In this case we do not need to update the data from the topic
            # We are processing many messages and we want the messages from the beging,
            # otherwise some topics not be in specific delta any more
            return self.queried_topics[topic]

        while page <= pages:
            url = "%s?topic=%s&delta=%s&page=%s" % (DATAGREPPER_URL, topic, self.delta, page)
            result = _query_url("%s&page=%s" % (url, page))
            if not result:
                return None

            jresult = json.loads(result)
            data.extend(jresult['raw_messages'])

            pages = int(jresult['pages'])
            page += 1

        self.queried_topics[topic] = data
        return data

    def query_all_topics(self):
        print("INFO: Querying topics from all pipelines...")
        for topic in VALID_PIPELINE_TOPICS:
            self._query_datagrepper(topic)
        print("INFO: All topics queried")


    def get_recent_prs(self, namespace="rpms"):
        """
        Check datagrepper for recent Pull Requests
        """
        pull_requests = []

        print("INFO: Getting PRs from the last %s seconds" % self.delta)
        topics = [NEW_PR_TOPIC, NEW_PR_COMMENT_TOPIC]
        data = []
        for topic in topics:
            msgs = self._query_datagrepper(topic)
            if msgs:
                data.extend(msgs)
        if not data:
            print("PASS: Got 0 PR messages")
            return None

        for pullrequest in data:
            # Skip PRs that are not from namespace
            pr_info = pullrequest['msg']['pullrequest']
            if namespace and pr_info['project']['namespace'] != namespace:
                continue
            # Skip commits on forks
            # if pr_info['path'].startswith("/srv/git/repositories/forks"):
            #    continue
            pull_requests.append(pullrequest['msg'])

        print("PASS: Got %s PR messages" % len(pull_requests))
        return pull_requests

    def get_recent_builds(self, namespace="rpms"):
        """
        Check datagrepper for recent Pull Requests
        """

        builds = []

        print("INFO: Getting Koji builds from the last %s seconds" % self.delta)
        data = self._query_datagrepper(KOJIBUILD_TOPIC)
        if not data:
            print("PASS: Got 0 Koji builds messages")
            return None

        for build in data:
            if build['msg']['new'] != 1:
                continue
            # Skip compose builds, not the best, but quicker than koji taskinfo
            if not re.match(".*\.(fc|el)\d+", build['msg']['release']):
                continue
            # Does not seem to be a valid package build
            if not build['msg']['request']:
                continue
            builds.append(build['msg'])

        print("PASS: Got %s Koji builds messages" % len(builds))
        return builds


    def get_pr_topic(self, project, branch, pr_id, topic, timeout):
        """
        Check datagrepper for specific topic related to the PR
        """
        count = 0
        topic_msg = None
        if not self.wait_complete:
            timeout = 0
        while not topic_msg:
            if count > timeout:
                return None

            count += 1
            # print("INFO: Searching topic %s for %s %s %s (%s / %s)" % (topic, project, branch, pr_id, count, timeout))
            data = self._query_datagrepper(topic)
            if not data:
                # Check if pipeline completed without sending expected topic message
                if topic != PR_PIPELINE_COMPLETE_TOPIC:
                    if self.get_pr_topic(project, branch, pr_id, PR_PIPELINE_COMPLETE_TOPIC, 0):
                        print("FAIL: pileline completed, but topic %s was never sent" % topic)
                        return None
                if count <= timeout:
                    time.sleep(60)
                continue
            for info in data:
                msg = info['msg']
                msg_repo = msg['repo']
                msg_branch = msg['branch']
                msg_rev = msg['rev'].replace("PR-", "")
                if msg_repo == project and msg_branch == branch and msg_rev == pr_id:
                    topic_msg = info
                    return info

            # Check if pipeline completed without sending expected topic message
            if topic != PR_PIPELINE_COMPLETE_TOPIC:
                if self.get_pr_topic(project, branch, pr_id, PR_PIPELINE_COMPLETE_TOPIC, 0):
                    print("FAIL: pileline completed, but topic %s was never sent" % topic)
                    return None

            if count <= timeout:
                time.sleep(60)

        return None

    def get_build_topic(self, project, branch, task_id, topic, timeout):
        """
        Check datagrepper for specific topic related to the koji build
        """
        count = 0
        topic_msg = None
        if not self.wait_complete:
            timeout = 0
        while not topic_msg:
            if count > timeout:
                return None

            count += 1
            # print("INFO: Searching topic %s for %s %s %s (%s / %s)" % (topic, project, branch, commit_id, count, timeout))
            data = self._query_datagrepper(topic)
            if not data:
                # Check if pipeline completed withtout sending expected topic message
                if topic != BUILD_PIPELINE_COMPLETE_TOPIC:
                    if self.get_build_topic(project, branch, task_id, BUILD_PIPELINE_COMPLETE_TOPIC, 0):
                        print("FAIL: pileline completed, but topic %s was never sent" % topic)
                        return None
                if count <= timeout:
                    time.sleep(60)
                continue

            for info in data:
                msg = info['msg']
                msg_repo = msg['repo']
                msg_branch = msg['branch']
                msg_id = msg['rev'].replace("kojitask-", "")
                if msg_repo == project and msg_branch == branch and msg_id == task_id:
                    topic_msg = info
                    return info

            # Check if pipeline completed without sending expected topic message
            if topic != BUILD_PIPELINE_COMPLETE_TOPIC:
                if self.get_build_topic(project, branch, task_id, BUILD_PIPELINE_COMPLETE_TOPIC, 0):
                    print("FAIL: pileline completed, but topic %s was never sent" % topic)
                    return None

            if count <= timeout:
                time.sleep(60)

        return None

    def verify_pull_request(self, project, branch, pr_id):
        """
        Check if PR ran properly on CI
        """
        pr_result = {"project" : project, "branch" : branch, "pr_id" : pr_id, "status" : None, "pipeline": "pullrequest"}
        if not has_jenkins_pipeline("pr", branch):
            topic_msg = self.get_pr_topic(project, branch, pr_id, PR_PIPELINE_PKG_IGNORED_TOPIC, 2)
            if not topic_msg:
                print("FAIL: %s %s %s Could not find topic %s" % (project, branch, pr_id, PR_PIPELINE_PKG_IGNORED_TOPIC))
                pr_result["status"] = INFRA_FAILURE
                return pr_result
            if "build_url" in topic_msg['msg']:
                pr_result["jenkins_build_url"] = topic_msg['msg']['build_url']
            print("SKIP: %s - %s does not contains tests" % (project,  branch))
            print("SKIP: %s there is no pipeline for pull request on branch %s" % (project, branch))
            pr_result["status"] = SKIP
            return pr_result

        if not check_tests(project, branch, pr_id):
            topic_msg = self.get_pr_topic(project, branch, pr_id, PR_PIPELINE_PKG_IGNORED_TOPIC, 2)
            if not topic_msg:
                print("FAIL: %s %s %s Could not find topic %s" % (project, branch, pr_id, PR_PIPELINE_PKG_IGNORED_TOPIC))
                pr_result["status"] = INFRA_FAILURE
                return pr_result
            if "build_url" in topic_msg['msg']:
                pr_result["jenkins_build_url"] = topic_msg['msg']['build_url']
            print("SKIP: %s - %s does not contains tests" % (project,  branch))
            pr_result["status"] = SKIP
            return pr_result

        print("INFO: Checking pipeline for PR %s %s %s" % (project, branch, pr_id))

        if not self.wait_complete:
            # in case the build still running we skip all other topics check
            topic_msg = self.get_pr_topic(project, branch, pr_id, PR_PIPELINE_PKG_QUEUED_TOPIC, 2)
            if not topic_msg:
                print("FAIL: %s %s %s Could not find topic %s" % (project, branch, pr_id, PR_PIPELINE_PKG_QUEUED_TOPIC))
                pr_result["status"] = INFRA_FAILURE
                return pr_result
            if "build_url" in topic_msg['msg']:
                pr_result["jenkins_build_url"] = topic_msg['msg']['build_url']
            topic_msg = self.get_pr_topic(project, branch, pr_id, PR_PIPELINE_COMPLETE_TOPIC, 0)
            if not topic_msg:
                print("SKIP: %s - %s - %s still running" % (project, branch, pr_id))
                pr_result["status"] = RUNNING
                return pr_result


        step_results = []

        pipeline_failed = False
        topic_jenkins_build = None
        for step in self.pipeline_steps['pr']:
            topic = step['topic']
            timeout = step['timeout']
            if pipeline_failed and topic != PR_PIPELINE_COMPLETE_TOPIC:
                # step will not execute if previous step failed
                step_results.append({'step': topic, 'status': SKIP})
                continue
            topic_msg = self.get_pr_topic(project, branch, pr_id, topic, timeout)
            if not topic_msg:
                pipeline_failed = True
                print("FAIL: Could not find topic %s" % topic)
                step_results.append({'step': topic, 'status': INFRA_FAILURE})
                continue
            if topic_msg['msg']['status'] not in step['status']:
                print("FAIL: Does not know how to handle status: %s" % topic_msg['msg']['status'])
                step_results.append({'step': topic, 'status': INFRA_FAILURE})
                continue

            if topic_msg['msg']['status'] != "SUCCESS":
                pipeline_failed = True
                print("FAIL: %s" % topic)
                step_results.append({'step': topic, 'status': step['status'][topic_msg['msg']['status']]})
                continue
            print("PASS: %s" % topic)
            step_results.append({'step': topic, 'status': PASS})

            # At this point Jenkins pipeline should have the build
            if topic == PR_PIPELINE_PKG_RUNNING_TOPIC:
                topic_jenkins_build = int(topic_msg['msg']['build_id'])
                topic_jenkins_build_url = topic_msg['msg']['build_url']


        if topic_jenkins_build:
            # Wait some time for jenkins build be completed
            build_info = get_jenkins_build_info("pr", branch, topic_jenkins_build)
            count = 5
            while build_info['building'] and count > 0:
                build_info = get_jenkins_build_info("pr", branch, topic_jenkins_build)
                time.sleep(60)
                count -= 1

            if count == 0:
                print("FAIL: Jenkins build did not finish: %s" % build_info)
                status = INFRA_FAILURE
                step_results.append({'step': "Jenkins build complete", 'status': INFRA_FAILURE})
            else:
                step_results.append({'step': "Jenkins build complete", 'status': PASS})
            print("INFO: Jenkins build URL: %s" % topic_jenkins_build_url)
            pr_result["jenkins_build_url"] = topic_jenkins_build_url
        else:
            print("FAIL: Could not find Jenkins build")
            step_results.append({'step': "Find Jenkins build", 'status': INFRA_FAILURE})

        pr_result["steps"] = step_results
        pr_result["status"] = PASS
        for result in step_results:
            # Set the status of first failure
            if result['status'] == INFRA_FAILURE or result['status'] == TEST_FAILURE:
                pr_result["status"] = result['status']
                break

        return pr_result

    def verify_kojibuild(self, project, branch, task_id):
        """
        Check if Kojibuild ran properly on CI
        """
        if branch.lower() == "rawhide":
            branch = "master"

        build_result = {"project" : project, "branch" : branch, "task_id" : task_id, "status" : None, "pipeline": "kojibuild"}
        if not has_jenkins_pipeline("kojibuild", branch):
            topic_msg = self.get_build_topic(project, branch, task_id, BUILD_PIPELINE_PKG_IGNORED_TOPIC, 2)
            if not topic_msg:
                print("FAIL: %s %s %s Could not find topic %s" % (project, branch, task_id, BUILD_PIPELINE_PKG_IGNORED_TOPIC))
                build_result["status"] = INFRA_FAILURE
                return build_result
            if "build_url" in topic_msg['msg']:
                build_result["jenkins_build_url"] = topic_msg['msg']['build_url']
            print("SKIP: %s there is no pipeline for koji build on branch %s" % (project, branch))
            build_result["status"] = SKIP
            return build_result

        if not check_tests(project,  branch):
            topic_msg = self.get_build_topic(project, branch, task_id, BUILD_PIPELINE_PKG_IGNORED_TOPIC, 2)
            if not topic_msg:
                print("FAIL: %s %s %s Could not find topic %s" % (project, branch, task_id, BUILD_PIPELINE_PKG_IGNORED_TOPIC))
                build_result["status"] = INFRA_FAILURE
                return build_result
            if "build_url" in topic_msg['msg']:
                build_result["jenkins_build_url"] = topic_msg['msg']['build_url']
            print("SKIP: %s - %s does not contains tests" % (project,  branch))
            build_result["status"] = SKIP
            return build_result

        print("INFO: Checking pipeline for BUILD %s %s %s" % (project, branch, task_id))

        if not self.wait_complete:
            # in case the build still running we skip all other topics check
            topic_msg = self.get_build_topic(project, branch, task_id, BUILD_PIPELINE_PKG_QUEUED_TOPIC, 2)
            if not topic_msg:
                print("FAIL: %s %s %s Could not find topic %s" % (project, branch, task_id, BUILD_PIPELINE_PKG_QUEUED_TOPIC))
                build_result["status"] = INFRA_FAILURE
                return build_result
            if "build_url" in topic_msg['msg']:
                build_result["jenkins_build_url"] = topic_msg['msg']['build_url']
            topic_msg = self.get_build_topic(project, branch, task_id, BUILD_PIPELINE_COMPLETE_TOPIC, 0)
            if not topic_msg:
                print("SKIP: %s - %s - %s still running" % (project, branch, task_id))
                build_result["status"] = RUNNING
                return build_result


        step_results = []

        pipeline_failed = False
        topic_jenkins_build = None
        for step in self.pipeline_steps['build']:
            topic = step['topic']
            timeout = step['timeout']
            if pipeline_failed and topic != BUILD_PIPELINE_COMPLETE_TOPIC:
                # step will not execute if previous step failed
                step_results.append({'step': topic, 'status': SKIP})
                continue
            topic_msg = self.get_build_topic(project, branch, task_id, topic, timeout)
            if not topic_msg:
                pipeline_failed = True
                print("FAIL: Could not find topic %s" % topic)
                step_results.append({'step': topic, 'status': step['no_msg']})
                continue
            if topic_msg['msg']['status'] not in step['status']:
                print("FAIL: Does not know how to handle status: %s" % topic_msg['msg']['status'])
                step_results.append({'step': topic, 'status': INFRA_FAILURE})
                continue
            if topic_msg['msg']['status'] != "SUCCESS":
                pipeline_failed = True
                print("FAIL: %s" % topic)
                step_results.append({'step': topic, 'status': step['status'][topic_msg['msg']['status']]})
                continue
            print("PASS: %s" % topic)
            step_results.append({'step': topic, 'status': PASS})

            if "build_id" in topic_msg['msg']:
                topic_jenkins_build = int(topic_msg['msg']['build_id'])
                topic_jenkins_build_url = topic_msg['msg']['build_url']


        if topic_jenkins_build:
            # Wait some time for jenkins build be completed
            build_info = get_jenkins_build_info("kojibuild", branch, topic_jenkins_build)
            count = 5
            while build_info['building'] and count > 0:
                build_info = get_jenkins_build_info("kojibuild", branch, topic_jenkins_build)
                time.sleep(60)
                count -= 1

            if count == 0:
                print("FAIL: Jenkins build did not finish: %s" % build_info)
                status = INFRA_FAILURE
                step_results.append({'step': "Jenkins build complete", 'status': INFRA_FAILURE})
            else:
                step_results.append({'step': "Jenkins build complete", 'status': PASS})
            print("INFO: Jenkins build URL: %s" % topic_jenkins_build_url)
            build_result["jenkins_build_url"] = topic_jenkins_build_url
        else:
            print("FAIL: Could not find Jenkins build")
            step_results.append({'step': "Find Jenkins build", 'status': INFRA_FAILURE})

        build_result["steps"] = step_results
        build_result["status"] = PASS
        for result in step_results:
            # Set the status of first failure
            if result['status'] == INFRA_FAILURE or result['status'] == TEST_FAILURE:
                build_result["status"] = result['status']
                break

        return build_result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-p', '--pipeline', dest='pipeline', choices=PIPELINES.keys(), default=None)
    args = parser.parse_args()

    start_time = int(time.time())

    monitor = Monitor()

    ci_message = os.getenv("CI_MESSAGE", None)
    if ci_message:
        msg = yaml.load(ci_message)
        messages = [msg]
    else:
        if not args.pipeline:
            messages = []
            prs = monitor.get_recent_prs()
            if prs:
                messages.extend(prs)
            builds = monitor.get_recent_builds()
            if builds:
                messages.extend(builds)
        elif args.pipeline == "pr":
            messages = monitor.get_recent_prs()
        elif args.pipeline == "kojibuild":
            messages = monitor.get_recent_builds()
        monitor.set_wait_complete(False)
        monitor.query_all_topics()

        if not messages:
            sys.exit(SKIP)

    result_log = {"results" : []}

    for message in messages:
        if 'pullrequest' in message:
            project = message['pullrequest']['project']['name']
            branch = message['pullrequest']['branch']
            pr_id = str(message['pullrequest']['id'])
            if message['pullrequest']['project']['namespace'] != "rpms":
                print("SKIP: %s %s %s - Pull request is not for rpms namespace" % (project, branch, pr_id))
                continue
            # Skip updated PRs if comment is not to rebuild
            if message['pullrequest']['comments'] and "citest" not in message['pullrequest']['comments'][-1]['comment']:
                print("SKIP: %s %s %s - Comment added to Pull request is not for rebuild" % (project, branch, pr_id))
                continue
            pr_result = monitor.verify_pull_request(project, branch, pr_id)
            result_log["results"].append(pr_result)
        elif 'build_id' in message:
            project = message['name']
            if not message['request']:
                print("SKIP: Does not seem to be a package build: %s" % message)
                continue
            build_tag = message['request'][1]
            branch = None
            task_id = str(message['task_id'])
            if not build_tag:
                print("FAIL: %s - could not find build tag for task %s" % (project, task_id))
                build_result = {"project" : project, "branch" : branch, "task_id" : task_id,
                                "status" : INFRA_FAILURE, "pipeline": "kojibuild"}
                result_log["results"].append(build_result)
                continue
            branch = re.sub("-.*", "", build_tag)
            build_result = monitor.verify_kojibuild(project, branch, task_id)
            result_log["results"].append(build_result)
        else:
            print("FAIL: Does not support ci_message: %s" % message)
            sys.exit(1)

    finish_time = int(time.time())
    result_log["start_time"] = start_time
    result_log["finish_time"] = finish_time
    result_log["delta"] = monitor.delta

    with open('result.json', 'w') as resultfile:
        json.dump(result_log, resultfile, indent=4, sort_keys=True, separators=(',', ': '))

    status = PASS
    for result in result_log['results']:
        # Set the status of first failure or skip
        if result['status'] != PASS:
            status = result['status']
            break


    sys.exit(status)
