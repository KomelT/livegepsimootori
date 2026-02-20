document.addEventListener("DOMContentLoaded", () => {
	const $ = django.jQuery;
	$('input[name="_download_gpx_button"]').on("click", (e) => {
		e.preventDefault();
		const encodedData = $("#id_locations_encoded").val();
		const positions = PositionArchive.fromEncoded(encodedData);
		const posArray = positions.getArray();
		let result = `<gpx xmlns="http://www.topografix.com/GPX/1/1" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.topografix.com/GPX/1/1 http://www.topografix.com/GPX/1/1/gpx.xsd" version="1.1" creator="Track.meshtrail.si">
  <metadata/>
  <trk>
    <name></name>
    <desc></desc>
    <trkseg>`;
		for (const point of posArray) {
			result += `
      <trkpt lat="${point[1]}" lon="${point[2]}"><time>${new Date(
				point[0],
			).toISOString()}</time></trkpt>`;
		}
		result += `
    </trkseg>
  </trk>
</gpx>`;

		const url = `data:text/xml;charset=utf-8,${result}`;
		const link = document.createElement("a");
		link.download = "device_data.gpx";
		link.href = url;
		document.body.appendChild(link);
		link.click();
		link.remove();
	});
});
