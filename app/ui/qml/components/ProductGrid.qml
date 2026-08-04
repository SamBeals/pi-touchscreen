import QtQuick
import QtQuick.Controls

GridView {
    id: root
    clip: true
    cellWidth: width / Math.max(1, App.browseColumns)
    cellHeight: Math.max(Theme.cardMinHeight + 24, 280)
    model: CatalogModel
    boundsBehavior: Flickable.StopAtBounds

    delegate: Item {
        width: root.cellWidth
        height: root.cellHeight

        ProductCard {
            anchors.fill: parent
            anchors.margins: Theme.gap / 2
            slotId: model.slotId
            name: model.name
            priceText: model.priceText
            stockText: model.stockText
            imageUrl: model.imageUrl
        }
    }

    EmptyState {
        anchors.centerIn: parent
        visible: root.count === 0
        message: "No products available"
    }

    onWidthChanged: App.setBrowseViewportWidth(width)
    Component.onCompleted: App.setBrowseViewportWidth(width)
}
