# IntelliJ project files for a uv Python project

IntelliJ IDEA (Ultimate or with the Python plugin) opens any folder, but writing these files
makes it open as a Python project with the right source roots and interpreter straight away.
Commit `.idea/` except the per-user files listed in `.gitignore` (`workspace.xml`, `shelf/`,
`usage.statistics.xml`).

Run `uv sync` first so `.venv/` exists. The SDK name below must match a Python SDK IntelliJ
knows; if it doesn't exist yet, IntelliJ shows "Configure Python interpreter" — pick
*Existing → `<project>/.venv/bin/python`* and it will be saved under this name. Don't edit
the global `jdk.table.xml` under `~/.config/JetBrains/`.

## `<Name>.iml` (project root)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<module type="PYTHON_MODULE" version="4">
  <component name="NewModuleRootManager">
    <content url="file://$MODULE_DIR$">
      <sourceFolder url="file://$MODULE_DIR$/src" isTestSource="false" />
      <sourceFolder url="file://$MODULE_DIR$/tests" isTestSource="true" />
      <excludeFolder url="file://$MODULE_DIR$/.venv" />
      <excludeFolder url="file://$MODULE_DIR$/.mypy_cache" />
      <excludeFolder url="file://$MODULE_DIR$/.pytest_cache" />
      <excludeFolder url="file://$MODULE_DIR$/.ruff_cache" />
      <excludeFolder url="file://$MODULE_DIR$/dist" />
    </content>
    <orderEntry type="jdk" jdkName="uv (<Name>)" jdkType="Python SDK" />
    <orderEntry type="sourceFolder" forTests="false" />
  </component>
  <component name="TestRunnerService">
    <option name="PROJECT_TEST_RUNNER" value="py.test" />
  </component>
</module>
```

## `.idea/modules.xml`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project version="4">
  <component name="ProjectModuleManager">
    <modules>
      <module fileurl="file://$PROJECT_DIR$/<Name>.iml" filepath="$PROJECT_DIR$/<Name>.iml" />
    </modules>
  </component>
</project>
```

## `.idea/misc.xml`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project version="4">
  <component name="ProjectRootManager" version="2" project-jdk-name="uv (<Name>)" project-jdk-type="Python SDK" />
</project>
```

## `.idea/vcs.xml`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project version="4">
  <component name="VcsDirectoryMappings">
    <mapping directory="" vcs="Git" />
  </component>
</project>
```

## `.idea/.name`

A single line: `<Name>`.

## Optional: run configuration for the tests

`.idea/runConfigurations/pytest.xml`:

```xml
<component name="ProjectRunConfigurationManager">
  <configuration default="false" name="pytest" type="tests" factoryName="py.test">
    <module name="<Name>" />
    <option name="SDK_HOME" value="$PROJECT_DIR$/.venv/bin/python" />
    <option name="WORKING_DIRECTORY" value="$PROJECT_DIR$" />
    <option name="_new_target" value="&quot;$PROJECT_DIR$/tests&quot;" />
    <option name="_new_targetType" value="&quot;PATH&quot;" />
    <method v="2" />
  </configuration>
</component>
```

## Opening it

Tell the user: *File → Open → `<dir>/<Name>`*, or from a shell `idea <dir>/<Name>` (the
Toolbox script). Don't launch the IDE yourself unless asked.
