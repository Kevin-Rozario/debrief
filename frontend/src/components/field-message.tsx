export function FieldMessage({
  id,
  message,
}: {
  id: string;
  message: string | null | undefined;
}) {
  if (message == null || message === "") {
    return null;
  }
  return (
    <p id={id} className="mt-2" role="alert">
      {message}
    </p>
  );
}
