"""Adapters for the university's web systems.

``gateway.CampusGateway`` is the only interface the rest of the application
uses. ``live.LiveCampusGateway`` talks to the real single sign-on, academic
records and learning platform; ``demo.DemoCampusGateway`` serves fixed sample
data so the product can be explored without a campus account.
"""
