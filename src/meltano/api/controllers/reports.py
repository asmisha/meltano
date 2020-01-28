from flask import Blueprint, jsonify, request

from .errors import InvalidFileNameError
from .reports_helper import ReportsHelper

from meltano.core.project import Project
from meltano.core.m5o.reports_service import ReportAlreadyExistsError, ReportsService

from meltano.api.api_blueprint import APIBlueprint
from meltano.api.security.auth import permit
from meltano.api.security.resource_filter import ResourceFilter, NameFilterMixin, Need
from meltano.api.security.readonly_killswitch import readonly_killswitch
from meltano.api.models import db

reportsBP = APIBlueprint("reports", __name__)


def reports_service():
    project = Project.find()
    return ReportsService(project)


class ReportFilter(NameFilterMixin, ResourceFilter):
    def __init__(self, *args):
        super().__init__(*args)

        self.needs(self.design_need)

    def design_need(self, permission_type, report):
        if permission_type == "view:reports":
            return Need("view:design", report["design"])


@reportsBP.errorhandler(ReportAlreadyExistsError)
def _handle(ex):
    report_name = ex.report["name"]
    return (
        jsonify(
            {
                "error": True,
                "code": f"A report with the name '{report_name}' already exists. Try renaming the report.",
            }
        ),
        409,
    )


@reportsBP.errorhandler(InvalidFileNameError)
def _handle(ex):
    return (
        jsonify(
            {
                "error": True,
                "code": f"The report name provided is invalid. Try a name without special characters.",
            }
        ),
        400,
    )


@reportsBP.route("/", methods=["GET"])
def index():
    reports = reports_service().get_reports()
    reports = ReportFilter().filter_all("view:reports", reports)

    return jsonify(reports)


@reportsBP.route("/embed/<token>", methods=["GET"])
def get_embed(token):
    reports_helper = ReportsHelper()
    embed = reports_helper.get_embed(db.session, token)
    report = reports_helper.get_report_by_name(embed.resource_id)

    return jsonify(report)


@reportsBP.route("/embed", methods=["POST"])
def embed():
    reports_helper = ReportsHelper()
    post_data = request.get_json()
    # TODO validate permission prior to making this public (maybe via the `permit`?)
    response_data = reports_helper.create_embed_snippet(db.session, post_data["name"])

    return jsonify(response_data)


@reportsBP.route("/<report_name>", methods=["POST"])
def load_report(report_name):
    permit("view:reports", report_name)

    reports_helper = ReportsHelper()
    post_data = request.get_json()
    response_data = (
        reports_helper.get_report_with_query_results(report_name)
        if post_data["has_results"]
        else reports_service().load_report(report_name)
    )

    permit("view:design", response_data["design"])

    return jsonify(response_data)


@reportsBP.route("/save", methods=["POST"])
@readonly_killswitch
def save_report():
    post_data = request.get_json()
    response_data = reports_service().save_report(post_data)
    return jsonify(response_data)


@reportsBP.route("/update", methods=["POST"])
@readonly_killswitch
def update_report():
    post_data = request.get_json()
    response_data = reports_service().update_report(post_data)
    return jsonify(response_data)
