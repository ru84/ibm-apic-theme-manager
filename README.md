# IBM API Connect Theme Manager

A Python-based tool to manage themes for the IBM API Connect Developer Portal. This utility streamlines theme development, deployment, and management across different environments.

## Motivation

When developing a theme for the IBM API Connect Developer Portal, the traditional workflow is extremely time-consuming. Developers must:
1. Create a ZIP archive of the local theme
2. Disable the existing custom theme to avoid name conflicts
3. Revert to a default theme
4. Delete the custom theme
5. Upload the ZIP file for the same custom theme with new code
6. Re-activate the theme

This tool automates this entire process, drastically reducing development time and eliminating error-prone manual steps. With a single command, you can compile, package, and deploy your theme changes to any environment.

## Features

- Upload and activate custom themes
- Compile SCSS to CSS
- Create theme archives for deployment
- Revert to default themes
- Clear Drupal cache
- OpenShift authentication and project management

## Prerequisites

- Python 3.x
- OpenShift CLI (`oc` command)
- Sass compiler (install via `npm install -g sass`)
- IBM API Connect Developer Portal access

## Configuration

Copy the sample configuration file and customize it for your environment:

```bash
cp theme_manager_config.sample.json theme_manager_config.json
```

Then edit `theme_manager_config.json` with your specific environment settings:

```json
{
  "defaults": {
    "environment": "development"
  },
  "themes": {
    "active_theme": "my_custom_theme",
    "default_theme": "connect_theme"
  },
  "environments": {
    "development": {
      "oc_project": "apiconnect-dev",
      "pod_name": "apiconnect-ptl-dev-www-0",
      "site_name": "dev.myapic.com",
      "platform_path": "/var/aegir/platforms/devportal-10.x-10.0.8.2-20250311-1629",
      "server_url": "https://api.ocp-dev.myapic.com:6443"
    },
    "production": {
      "oc_project": "apiconnect",
      "pod_name": "apiconnect-ptl-prod-www-0",
      "site_name": "developer.myapic.com",
      "platform_path": "/var/aegir/platforms/devportal-10.x-10.0.8.2-20250311-1629",
      "server_url": "https://api.ocp.myapic.com:6443"
    }
  }
}
```

## Usage

### Login to OpenShift

```bash
./theme-manager.py login
```

### Check Theme Status

```bash
./theme-manager.py status
```

### Upload and Activate a Theme

```bash
./theme-manager.py upload --theme my_custom_theme
```

### Create a ZIP Archive Without Uploading

```bash
./theme-manager.py zip --theme my_custom_theme
```

### Revert to Default Theme

```bash
./theme-manager.py revert --env production
```

### Clear Drupal Cache

```bash
./theme-manager.py cache-clear
```

## Creating a New Subtheme

1. **Create a New Theme Directory**

   Start by creating a new directory for your custom theme:

   ```bash
   mkdir my_new_theme
   cd my_new_theme
   ```

2. **Set Up Theme Files**

   Create the basic structure:

   ```bash
   mkdir -p css js scss templates
   touch my_new_theme.info.yml
   ```

3. **Create Theme Configuration**

   Edit `my_new_theme.info.yml`:

   ```yaml
   name: My New Theme
   type: theme
   description: 'Custom theme for IBM API Connect Developer Portal'
   core: 8.x
   base theme: connect_theme
   
   libraries:
     - my_new_theme/global-styling
   
   regions:
     header: Header
     content: Content
     sidebar_first: 'Sidebar first'
     sidebar_second: 'Sidebar second'
     footer: Footer
   ```

4. **Set Up Library Definition**

   Create `my_new_theme.libraries.yml`:

   ```yaml
   global-styling:
     css:
       theme:
         css/style.css: {}
     js:
       js/script.js: {}
   ```

5. **Create SCSS Structure**

   Create your main SCSS file at `scss/style.scss`:

   ```scss
   // Import base styles from parent theme
   @import '../../../connect_theme/scss/variables';
   
   // Override variables
   $primary-color: #0f62fe;
   $secondary-color: #393939;
   
   // Custom styles
   body {
     font-family: 'IBM Plex Sans', sans-serif;
   }
   
   // Component styles
   @import 'components/buttons';
   @import 'components/navigation';
   ```

6. **Create Template Overrides**

   Copy templates from the parent theme that you want to customize:

   ```bash
   mkdir -p templates/page templates/node
   cp ../connect_theme/templates/page/page.html.twig templates/page/
   ```

7. **Configure Theme Manager**

   Update `theme_manager_config.json` with your new theme:

   ```json
   "themes": {
     "active_theme": "my_new_theme",
     "default_theme": "connect_theme"
   }
   ```

8. **Compile SCSS and Upload**

   Run the theme manager to compile SCSS and upload your theme:

   ```bash
   ./theme-manager.py upload
   ```

9. **Verify Installation**

   Check that your theme is active:

   ```bash
   ./theme-manager.py status
   ```

## Tips for Theme Development

- Make incremental changes and test frequently
- Use Drupal's theme debug mode to identify template suggestions
- Create a local development environment for faster iteration
- Use SCSS variables for consistent styling across components
- Follow IBM Design Language guidelines for best results

## Troubleshooting

- If theme changes don't appear, try clearing the cache with `cache-clear`
- Check OpenShift pod logs for Drupal errors
- Ensure your SCSS compiles correctly before uploading
- Verify file permissions in the container

## License

This project is licensed under the MIT License - see the LICENSE file for details.