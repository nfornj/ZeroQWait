import NavbarBreadcrumbs from './NavbarBreadcrumbs';

export default function Header() {
  return (
    <div className="hidden md:flex w-full items-center pb-2">
      <NavbarBreadcrumbs />
    </div>
  );
}
