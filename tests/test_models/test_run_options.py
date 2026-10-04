# File: tests/test_models/test_run_options.py

from restikls.models.run_options import RunOptions


def test_run_options_defaults():
    """
    Test that instantiating RunOptions without arguments 
    assigns the correct default values.
    """
    options = RunOptions()
    
    assert options.capture_output is True
    assert options.text is True
    assert options.shell is False
    assert options.timeout == 60
    assert options.check is False
    assert options.env == {}


def test_run_options_custom_initialization():
    """
    Test that explicit arguments correctly override default values.
    """
    custom_env = {"RESTIC_PASSWORD": "supersecret", "RESTIC_REPOSITORY": "/srv/backup"}
    
    options = RunOptions(
        capture_output=False,
        text=False,
        shell=True,
        timeout=120,
        check=True,
        env=custom_env
    )
    
    assert options.capture_output is False
    assert options.text is False
    assert options.shell is True
    assert options.timeout == 120
    assert options.check is True
    assert options.env == custom_env


def test_run_options_env_default_factory_isolation():
    """
    Test the edge case where mutable defaults can be shared across instances.
    Ensures that the default_factory=dict creates an isolated dictionary 
    for each new instance.
    """
    options_a = RunOptions()
    options_b = RunOptions()
    
    # Modify the environment dictionary of the first instance
    options_a.env["NEW_VAR"] = "value"
    
    # Verify the second instance's dictionary remains unmodified and empty
    assert "NEW_VAR" in options_a.env
    assert "NEW_VAR" not in options_b.env
    assert options_b.env == {}


def test_run_options_attribute_mutation():
    """
    Test that attributes can be modified after initialization, 
    as this is a standard mutable dataclass.
    """
    options = RunOptions()
    
    # Modify properties post-initialization
    options.timeout = 300
    options.shell = True
    
    assert options.timeout == 300
    assert options.shell is True