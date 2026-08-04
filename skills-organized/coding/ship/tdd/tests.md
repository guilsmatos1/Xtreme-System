# Good and Bad Tests

## Good

Observable behavior through a public seam (pytest):

```python
def test_usuario_with_valid_credentials_receives_token(client, usuario_fixture):
    response = client.post("/login", data={"username": usuario_fixture.email, "password": "secret"})
    assert response.status_code == 200
    assert "access_token" in response.json()
```

- Behavior callers care about
- Public API only
- Survives internal refactors
- Describes WHAT, not HOW

## Bad

```python
def test_login_calls_verify_password(mocker):
    spy = mocker.spy(auth_core, "verify_password")
    login(...)
    spy.assert_called_once()
```

Red flags: mocking internal collaborators, asserting call graphs, snapshots of private structure.
