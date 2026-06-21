from marshmallow import Schema, fields


class ComponentHealthSchema(Schema):
    component = fields.String(required=True)
    status = fields.String(required=True)
    message = fields.String(required=True)
    latency_ms = fields.Float(required=True)
    details = fields.Dict(required=False)


class CompleteHealthSchema(Schema):
    service = fields.String(required=True)
    environment = fields.String(required=True)
    status = fields.String(required=True)

    checks = fields.Dict(
        keys=fields.String(),
        values=fields.Nested(ComponentHealthSchema()),
        required=True,
    )